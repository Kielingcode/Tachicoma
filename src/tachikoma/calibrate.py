"""CalibrationRunner — FR-5 formal 判据执行器(v2.5:按 bypassable 分流)。

bypassable fact(ProceduralDependency)的 formal gate:
  median(memory-off cost) ≥ 1.5 × median(oracle-informed cost)
  ∧ tool-discovery 率 ≥ 0.6 ∧ eventual ≥ 0.9
direct_leakage 作为诊断量逐 run 报告(每次出现需人工泄漏分析),不作 gate。
oracle-informed runs 是校准协议的一部分——eval 侧合法使用 oracle(FR-43 防火墙
只约束 learning path)。校准不学习(learn 永远 False,不触碰任何 store)。
"""

from __future__ import annotations

import argparse
import json
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path

from tachikoma.adapter import CodeKittyAdapter
from tachikoma.generator import FACT_ORACLE, LEARNING_VARIANTS, materialize
from tachikoma.path_classifier import Episode, classify
from tachikoma.runner import events_to_actions, first_try_success, success_check

GATE = {"cost_ratio": 1.5, "discovery": 0.6, "eventual": 0.9}


def _informed_block() -> str:
    """校准内置的 oracle-informed 注入(与 P0b smoke 的 oi 臂同文案)。"""
    return ("Relevant memory from previous tasks in this repository "
            "(memory_id: mem_cal, status: active_correlational — observed useful "
            "pattern, not yet causally verified):\n"
            f"- trigger: after editing {FACT_ORACLE['after_edit']}\n"
            f"- instruction: run `{FACT_ORACLE['must_run']}` to regenerate derived "
            "record artifacts before final validation\n"
            "- evidence: 2 supporting task families, 0 contradictions")


def _probe(variant_id: str, model: str, workspace_root: Path, informed: bool,
           adapter: CodeKittyAdapter) -> dict:
    rid = f"cal-{'oi' if informed else 'off'}-{variant_id}-{uuid.uuid4().hex[:6]}"
    ws = Path(workspace_root) / rid
    bundle = materialize(variant_id, ws)
    res = adapter.run(bundle.prompt, ws, model,
                      injection_block=_informed_block() if informed else "")
    eventual = success_check(ws)
    ep = Episode(actions=events_to_actions(res.events), eventual_success=eventual,
                 cost_steps=res.cost_steps, cost_tokens=res.cost_tokens,
                 memory_injected=informed)
    pc = classify(ep)
    return {"run_id": rid, "variant_id": variant_id, "informed": informed,
            "eventual": eventual, "first_try": first_try_success(ep),
            "cost_steps": res.cost_steps, "cost_tokens": res.cost_tokens,
            "path_class": pc.as_dict(), "session": res.session_path}


def formal_calibration(model: str, workspace_root: Path, n: int = 20, k_informed: int = 3,
                       variants: list[str] | None = None,
                       adapter: CodeKittyAdapter | None = None,
                       on_result=None) -> dict:
    """N 次 memory-off + k 次 oracle-informed,产出 gate 判定报告。"""
    adapter = adapter or CodeKittyAdapter()
    variants = variants or LEARNING_VARIANTS
    runs: list[dict] = []
    for i in range(n):
        r = _probe(variants[i % len(variants)], model, workspace_root, False, adapter)
        runs.append(r)
        if on_result:
            on_result(r)
    for i in range(k_informed):
        r = _probe(variants[i % len(variants)], model, workspace_root, True, adapter)
        runs.append(r)
        if on_result:
            on_result(r)

    off = [r for r in runs if not r["informed"]]
    oi = [r for r in runs if r["informed"]]
    discovery = _rate(off, lambda r: r["path_class"]["intended_procedure_discovered"])
    eventual = _rate(off, lambda r: r["eventual"])
    leaks = [r["run_id"] for r in off if r["path_class"]["direct_leakage"]]
    med_off = statistics.median(r["cost_steps"] for r in off) if off else None
    med_oi = statistics.median(r["cost_steps"] for r in oi) if oi else None
    ratio = (med_off / med_oi) if (med_off and med_oi) else None

    verdict = (ratio is not None and ratio >= GATE["cost_ratio"]
               and discovery >= GATE["discovery"] and eventual >= GATE["eventual"])
    return {
        "model": model, "n": n, "k_informed": k_informed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gate": GATE, "accepted": verdict,
        "discovery_rate": discovery, "eventual_rate": eventual,
        "median_cost_off": med_off, "median_cost_informed": med_oi,
        "cost_ratio": ratio,
        "direct_leakage_runs": leaks,           # 诊断量:逐条需人工泄漏分析
        "direct_leakage_rate": len(leaks) / len(off) if off else None,
        "runs": runs,
    }


def _rate(rows, pred) -> float:
    return sum(1 for r in rows if pred(r)) / len(rows) if rows else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description="FR-5 formal calibration (v2.5 gate)")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--k-informed", type=int, default=3)
    ap.add_argument("--workspace-root", default="/tmp/tachikoma_cal")
    ap.add_argument("--out", default="spikes/p0b/calibration_report.json")
    args = ap.parse_args()
    report = formal_calibration(
        args.model, Path(args.workspace_root), n=args.n, k_informed=args.k_informed,
        on_result=lambda r: print(f"  {r['run_id']}: eventual={r['eventual']} "
                                  f"steps={r['cost_steps']} "
                                  f"disc={r['path_class']['intended_procedure_discovered']}",
                                  flush=True))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"accepted={report['accepted']} ratio={report['cost_ratio']} "
          f"discovery={report['discovery_rate']} eventual={report['eventual_rate']}")
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()
