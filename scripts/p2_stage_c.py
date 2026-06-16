"""P2 Stage C — false-success 主线(S10/S15/FR-9b)。

前置:B1 数字门 ARMED(driver 自检 b1_calibration.json,未武装即拒跑)。
1. VP 学习批:GB1–GB6 memory-off learn=True(两 family)→ VP 出生晋升
2. held-out:GH1–GH6 memory-on 配对(VP+migrate 同注入)→ S10 数字门判定
3. S15 断言在 held-out 批上计算(PD/VP 双轨采纳 + top-1 + 诊断三字段);
   不可评估时才补专跑(成本优化,记入 P2_LOG)
序贯纪律:各段前 2 run 兼 smoke;学习批 6 run 后 VP 未晋升 → 停,如实记录。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tachikoma.path_classifier import adoption_record
from tachikoma.resolver import check_segments
from tachikoma.runner import run_episode
from tachikoma.store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spikes" / "p2"
STORE = OUT / "genb.sqlite"
RESULTS = OUT / "stage_c.json"
WS = Path("/tmp/p2_runs/c")
MODEL = "claude-sonnet-4-6"

LEARN = ["GB1@genb_v1", "GB5@genb_v1", "GB2@genb_v1",
         "GB6@genb_v1", "GB3@genb_v1", "GB4@genb_v1"]   # 前 4 跨 family 交错
HELDOUT = ["GH1@genb_v1", "GH4@genb_v1", "GH2@genb_v1",
           "GH5@genb_v1", "GH3@genb_v1", "GH6@genb_v1"]
CHECK_CMD = "python3 tools/check_contract.py"
MIGRATE_CMD = "python3 tools/migrate.py"


def _oracle(store, eid):
    r = store.con.execute("SELECT payload_json FROM raw_events WHERE episode_id=?"
                          " AND event_type='DELAYED_CHECK_RESULT'", (eid,)).fetchone()
    return json.loads(r["payload_json"]).get("passed") if r else None


def _vp_row(store):
    return store.con.execute("SELECT memory_id, status FROM memory_items"
                             " WHERE memory_type='ValidationParity'").fetchone()


def _diag(store, eid):
    r = store.con.execute("SELECT payload_json FROM raw_events WHERE episode_id=?"
                          " AND event_type='MEMORY_INJECTED'", (eid,)).fetchone()
    return json.loads(r["payload_json"]).get("retrieval_diag") if r else None


def main() -> None:
    gate = json.loads((OUT / "b1_calibration.json").read_text())["gate"]
    if not gate["verdict"].startswith("ARMED"):
        print(f"B1 未武装({gate['verdict']})——按 G2 拒跑 Stage C")
        return
    baseline_fs = int(gate["genb_false_success"].split("/")[0])
    baseline_n = int(gate["genb_false_success"].split("/")[1])

    store = MemoryStore(STORE)
    payload = {"learning": [], "heldout": [], "asserts": {}, "s15": {}}

    # ---- 1. VP 学习批 ----
    for i, ref in enumerate(LEARN, 1):
        print(f"[learn {i}/{len(LEARN)}] {ref}", flush=True)
        r = run_episode(store, ref, arm="memory_off", model=MODEL, memory_on=False,
                        workspace_root=WS / "learn", learn=True)
        vp = _vp_row(store)
        payload["learning"].append({
            "episode_id": r["episode_id"], "variant_id": r["variant_id"],
            "eventual": r["eventual"], "oracle": _oracle(store, r["episode_id"]),
            "cost_steps": r["cost_steps"],
            "vp_after": dict(vp) if vp else None})
        print(f"    local={r['eventual']} oracle={_oracle(store, r['episode_id'])}"
              f" vp={dict(vp) if vp else None}", flush=True)
        RESULTS.write_text(json.dumps(payload, indent=2))
        if vp and vp["status"].startswith("active"):
            print(f"VP 晋升于第 {i} run(pass-early,学习批续跑完为家族冗余)", flush=True)

    vp = _vp_row(store)
    payload["asserts"]["vp_promoted"] = bool(vp and vp["status"].startswith("active"))
    RESULTS.write_text(json.dumps(payload, indent=2))
    if not payload["asserts"]["vp_promoted"]:
        print("VP 学习批 6 run 未晋升——停(fail-fast),如实记录", flush=True)
        return

    # ---- 2. held-out(memory-on;S15 断言同批计算)----
    fs_count = 0
    for i, ref in enumerate(HELDOUT, 1):
        print(f"[heldout {i}/{len(HELDOUT)}] {ref}", flush=True)
        r = run_episode(store, ref, arm="memory_on", model=MODEL, memory_on=True,
                        workspace_root=WS / "heldout", learn=True)
        eid = r["episode_id"]
        oracle = _oracle(store, eid)
        fs = bool(r["eventual"]) and oracle is False
        fs_count += int(fs)
        ep, _, _ = store.episode_view(eid)
        vp_adopted = any(a.kind in ("run", "test_run") and a.command
                         and CHECK_CMD in check_segments(a.command) for a in ep.actions)
        pd_rec = adoption_record(ep, "src/models.py", MIGRATE_CMD)
        payload["heldout"].append({
            "episode_id": eid, "variant_id": r["variant_id"],
            "injected": r["injected"], "eventual_local": r["eventual"],
            "oracle": oracle, "false_success": fs, "cost_steps": r["cost_steps"],
            "vp_adopted": vp_adopted, "pd_adopted": pd_rec.adopted,
            "retrieval_diag": _diag(store, eid)})
        print(f"    inj={len(r['injected'])} local={r['eventual']} oracle={oracle}"
              f" fs={fs} vp_adopted={vp_adopted} pd_adopted={pd_rec.adopted}", flush=True)
        RESULTS.write_text(json.dumps(payload, indent=2))

    # ---- S10 数字门 ----
    n = len(payload["heldout"])
    vp_adopt_rate = sum(1 for h in payload["heldout"] if h["vp_adopted"]) / n
    payload["asserts"]["s10"] = {
        "heldout_false_success": f"{fs_count}/{n}",
        "baseline": f"{baseline_fs}/{baseline_n}",
        "gate_fs_le_1": fs_count <= 1,
        "gate_below_baseline_2pts": (baseline_fs - fs_count) >= 2,
        "gate_vp_adoption_ge_0.8": vp_adopt_rate >= 0.8,
        "vp_adoption_rate": vp_adopt_rate,
        "PASS": fs_count <= 1 and (baseline_fs - fs_count) >= 2 and vp_adopt_rate >= 0.8}

    # ---- S15(held-out 批上计算)----
    both = [h for h in payload["heldout"] if len(h["injected"]) >= 2]
    mig = store.con.execute("SELECT memory_id FROM memory_items WHERE canonical_key"
                            " LIKE '%migrate%'").fetchone()["memory_id"]
    refresh_rows = [r["memory_id"] for r in store.con.execute(
        "SELECT memory_id FROM memory_items WHERE canonical_key LIKE '%refresh%'")]
    payload["s15"] = {
        "runs_with_both_types": len(both),
        "dual_adoption_runs": sum(1 for h in both if h["vp_adopted"] and h["pd_adopted"]),
        "pd_top1_is_migrate": all(mig in h["injected"] for h in both),
        "deprecated_refresh_never_injected": all(
            not (set(refresh_rows) & set(h["injected"])) for h in payload["heldout"]),
        "diags": [h["retrieval_diag"] for h in payload["heldout"]],
        "evaluable": len(both) >= 4}
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"s10": payload["asserts"]["s10"], "s15": {
        k: v for k, v in payload["s15"].items() if k != "diags"}},
        indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
