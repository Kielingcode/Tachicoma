"""DemoDriver — 三臂配对 demo(FR-39 + plan v1.1 Stage 6)。

臂 A:memory-off 基线(Sonnet,即配对的 off 侧)
臂 B:自学(Sonnet 发现批 → 学习 → Sonnet held-out 注入)
臂 C:跨模型(同 harness,Fable 发现批 → 学习 → Sonnet held-out 注入)
发现批构成:3×add-field + 3×rename-field(晋升门要求 distinct_task_family ≥ 2);
某 family 零发现 → 补跑该 family ≤2 次。三臂共享同一 held-out 任务集(不相交参数)。
Verification #4:臂 B/C 相对臂 A 配对步数差中位数 ≥ 30%(与 §10 同标)。
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from tachikoma.generator import HELDOUT_VARIANTS
from tachikoma.oracle_eval import fact_precision, injection_precision, oracle_key
from tachikoma.runner import run_episode
from tachikoma.store import MemoryStore

DISCOVERY_BATCH = ["A1", "A2", "A3", "B1", "B2", "B3"]   # 3×add-field + 3×rename-field
FAMILY_OF = {"A1": "add-field", "A2": "add-field", "A3": "add-field",
             "B1": "rename-field", "B2": "rename-field", "B3": "rename-field"}
TARGET_MEDIAN_DELTA = 0.30


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _has_active(store: MemoryStore) -> bool:
    return store.con.execute(
        "SELECT COUNT(*) c FROM memory_items WHERE status LIKE 'active%'").fetchone()["c"] > 0


def _families_with_positive_claims(store: MemoryStore) -> set[str]:
    rows = store.con.execute(
        "SELECT DISTINCT ep.family_id f FROM claims c JOIN episodes ep"
        " ON c.episode_id=ep.episode_id WHERE c.polarity>0").fetchall()
    return {r["f"] for r in rows if r["f"]}


def discovery_phase(store: MemoryStore, arm: str, model: str, workspace_root: Path,
                    records: list[dict]) -> None:
    for v in DISCOVERY_BATCH:
        _log(f"{arm} discovery {v} ({model})")
        records.append(run_episode(store, v, arm=f"{arm}_discovery", model=model,
                                   memory_on=False, workspace_root=workspace_root,
                                   learn=True))
    # 补跑规则(plan 小口 1):缺正向证据的 family 补 ≤2 次
    for fam in ("add-field", "rename-field"):
        retries = 0
        while fam not in _families_with_positive_claims(store) and retries < 2:
            v = next(vid for vid, f in FAMILY_OF.items() if f == fam)
            retries += 1
            _log(f"{arm} retry {v} (family {fam} has no positive claim yet)")
            records.append(run_episode(store, v, arm=f"{arm}_discovery_retry", model=model,
                                       memory_on=False, workspace_root=workspace_root,
                                       learn=True))
    _log(f"{arm} discovery done; active memory present: {_has_active(store)}")


def run_demo(out_dir: Path, workspace_root: Path, sonnet: str, frontier: str,
             heldout_reps: int = 2, skip_discovery: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    store_a = MemoryStore(out_dir / "arm_a.sqlite")   # 仅记录,不学习不注入
    store_b = MemoryStore(out_dir / "arm_b.sqlite")
    store_c = MemoryStore(out_dir / "arm_c.sqlite")
    records: list[dict] = []

    if not skip_discovery:
        discovery_phase(store_b, "arm_b", sonnet, workspace_root, records)
        discovery_phase(store_c, "arm_c", frontier, workspace_root, records)
    else:
        _log(f"skip discovery; active: b={_has_active(store_b)} c={_has_active(store_c)}")

    heldout_tasks = [v for v in HELDOUT_VARIANTS for _ in range(heldout_reps)]
    pairs = []
    for i, v in enumerate(heldout_tasks):
        _log(f"held-out task {i + 1}/{len(heldout_tasks)} ({v})")
        a = run_episode(store_a, v, arm="arm_a", model=sonnet, memory_on=False,
                        workspace_root=workspace_root, learn=False)
        b = run_episode(store_b, v, arm="arm_b", model=sonnet, memory_on=True,
                        workspace_root=workspace_root, learn=False)
        c = run_episode(store_c, v, arm="arm_c", model=sonnet, memory_on=True,
                        workspace_root=workspace_root, learn=False)
        records += [a, b, c]
        pairs.append({"task": f"{v}#{i}", "variant": v,
                      "a": a, "b": b, "c": c})

    report = _build_report(store_b, store_c, pairs, records)
    (out_dir / "demo_report.json").write_text(json.dumps(report, indent=2, default=str),
                                              encoding="utf-8")
    (out_dir / "demo_report.md").write_text(_markdown(report), encoding="utf-8")
    _log(f"report -> {out_dir}/demo_report.md")
    return report


def _build_report(store_b, store_c, pairs, records) -> dict:
    def deltas(key):
        return [(p["a"]["cost_steps"] - p[key]["cost_steps"]) / p["a"]["cost_steps"]
                for p in pairs if p["a"]["cost_steps"]]

    okey = oracle_key(records[0]["fact_oracle"])
    inj_oracle_b = {r["episode_id"]: okey for r in records if r["arm"] == "arm_b"}
    inj_oracle_c = {r["episode_id"]: okey for r in records if r["arm"] == "arm_c"}
    med_b = statistics.median(deltas("b")) if pairs else None
    med_c = statistics.median(deltas("c")) if pairs else None
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pairs": [{
            "task": p["task"],
            "steps": {k: p[k]["cost_steps"] for k in "abc"},
            "tokens": {k: p[k]["cost_tokens"] for k in "abc"},
            "first_try": {k: p[k]["first_try"] for k in "abc"},
            "eventual": {k: p[k]["eventual"] for k in "abc"},
            "adopted": {k: p[k]["path_class"]["intended_procedure_adopted"] for k in "bc"},
            "injected": {k: p[k]["injected"] for k in "bc"},
        } for p in pairs],
        "median_step_delta_vs_a": {"arm_b": med_b, "arm_c": med_c},
        "target_median_delta": TARGET_MEDIAN_DELTA,
        "verdict": {
            "arm_b": med_b is not None and med_b >= TARGET_MEDIAN_DELTA,
            "arm_c": med_c is not None and med_c >= TARGET_MEDIAN_DELTA,
        },
        "oracle_eval": {
            "arm_b": {**fact_precision(store_b, {okey}),
                      **injection_precision(store_b, inj_oracle_b)},
            "arm_c": {**fact_precision(store_c, {okey}),
                      **injection_precision(store_c, inj_oracle_c)},
        },
        "records": records,
    }


def _markdown(report: dict) -> str:
    lines = ["# P0b 三臂 demo 报告", "",
             f"> {report['created_at']} · 臂 A=memory-off · 臂 B=自学(Sonnet)· "
             "臂 C=跨模型(Fable 发现 → Sonnet 执行)", "",
             "| task | A steps | B steps | C steps | B adopted | C adopted | "
             "A first-try | B first-try | C first-try |",
             "|---|---|---|---|---|---|---|---|---|"]
    for p in report["pairs"]:
        s, ft, ad = p["steps"], p["first_try"], p["adopted"]
        lines.append(f"| {p['task']} | {s['a']} | {s['b']} | {s['c']} | "
                     f"{ad['b']} | {ad['c']} | {ft['a']} | {ft['b']} | {ft['c']} |")
    md = report["median_step_delta_vs_a"]
    v = report["verdict"]
    lines += ["",
              f"**配对步数差中位数 vs 臂 A**:臂 B = {md['arm_b']:.0%}(≥30%: {v['arm_b']}),"
              f"臂 C = {md['arm_c']:.0%}(≥30%: {v['arm_c']})" if md["arm_b"] is not None
              else "**无配对数据**",
              "",
              "## Oracle eval(FR-43,eval-only)", "",
              "```json",
              json.dumps(report["oracle_eval"], indent=2),
              "```"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="P0b three-arm paired demo (FR-39)")
    ap.add_argument("--sonnet", default="claude-sonnet-4-6")
    ap.add_argument("--frontier", default="claude-fable-5")
    ap.add_argument("--out-dir", default="spikes/p0b/demo")
    ap.add_argument("--workspace-root", default="/tmp/tachikoma_demo")
    ap.add_argument("--heldout-reps", type=int, default=2)
    ap.add_argument("--skip-discovery", action="store_true",
                    help="复用既有 store 的发现批(断点续跑)")
    args = ap.parse_args()
    run_demo(Path(args.out_dir), Path(args.workspace_root),
             args.sonnet, args.frontier, heldout_reps=args.heldout_reps,
             skip_discovery=args.skip_discovery)


if __name__ == "__main__":
    main()
