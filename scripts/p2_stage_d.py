"""P2 Stage D — S13b live:一条候选的 utility canary 确认 → 逐级降一档。

候选 = Stage A shadow 的 low_utility_candidate(wasteful.sqlite 的 refresh;
兜底裁决方案 A——shadow 只定优先级,不定存在性)。
判定:adopted ∧ paired median step_delta ≤ 噪声门 ∧ 无 outcome 收益
  → active_* 降一档(verified→correlational→candidate),reason=low_utility。
live 反而显示真实收益(median > 门)→ 如实记录、不降级,S13b live 转 P2-full。
shadow 与 live 不一致(候选根本未被采纳等)→ 停修判据。
"""

import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tachikoma.canary import evaluate, run_canary_pairs
from tachikoma.store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spikes" / "p2"
SRC = ROOT / "spikes" / "p1" / "wasteful.sqlite"
STORE = OUT / "s13b.sqlite"
RESULTS = OUT / "stage_d.json"
WS = Path("/tmp/p2_runs/d")
MODEL = "claude-sonnet-4-6"
GATE, THETA = 6, 0.8                       # B1 同日参考(P1 锁定值沿用,P2_LOG 记)
PAIRS = ["W1@shim_v1", "W2@shim_v1"]
COND = ["W3@shim_v1"]
DOWN = {"active_verified": "active_correlational",
        "active_correlational": "candidate"}


def main() -> None:
    if not STORE.exists():
        shutil.copy(SRC, STORE)
    store = MemoryStore(STORE)
    row = store.con.execute("SELECT memory_id, status FROM memory_items"
                            " WHERE canonical_key LIKE '%refresh%'").fetchone()
    mid = row["memory_id"]
    payload = {"candidate": {"memory_id": mid, "status_pre": row["status"]},
               "verdict": None, "asserts": {}}
    print(f"candidate {mid} status={row['status']}", flush=True)

    print("== utility canary: 2 pairs @shim ==", flush=True)
    run_canary_pairs(store, PAIRS, MODEL, WS)
    v = evaluate(store, mid, step_delta_gate=GATE, theta_adopt=THETA)
    print(json.dumps(v, indent=1), flush=True)
    if v["median_step_delta"] is not None and abs(v["median_step_delta"] - GATE) <= 1:
        print("== borderline → +1 pair ==", flush=True)
        run_canary_pairs(store, COND, MODEL, WS, pair_offset=len(PAIRS))
        v = evaluate(store, mid, step_delta_gate=GATE, theta_adopt=THETA)
    payload["verdict"] = v

    adopted = (v["adoption_rate"] or 0) >= THETA
    low_utility = adopted and v["median_step_delta"] is not None \
        and v["median_step_delta"] <= GATE and v["pos_flips"] == 0
    payload["asserts"]["adopted"] = adopted
    payload["asserts"]["low_utility_confirmed"] = low_utility
    payload["asserts"]["shadow_live_consistent"] = adopted  # shadow 前提=被采纳

    if low_utility:
        new = DOWN.get(row["status"])
        if new:
            now = datetime.now(timezone.utc).isoformat()
            store.con.execute(
                "UPDATE memory_items SET status=?, causal_verified=0, updated_at=?"
                " WHERE memory_id=?", (new, now, mid))
            store.con.execute(
                "INSERT INTO status_history (memory_id, old_status, new_status, reason,"
                " evidence_snapshot_json, job_id, created_at) VALUES (?,?,?,?,?,?,?)",
                (mid, row["status"], new,
                 f"low_utility (FR-25b): utility canary median_delta="
                 f"{v['median_step_delta']} <= gate {GATE}, adoption="
                 f"{v['adoption_rate']}, pos_flips=0",
                 json.dumps(v), f"s13b_{uuid.uuid4().hex[:8]}", now))
            store.con.commit()
            payload["demotion"] = {"from": row["status"], "to": new}
            print(f"S13b live:{row['status']} → {new}(reason=low_utility)", flush=True)
    elif adopted:
        payload["demotion"] = None
        print("live 显示真实收益——不降级,如实记录,S13b live → P2-full", flush=True)
    else:
        print("候选未被采纳:shadow/live 不一致——停,回去修判据", flush=True)

    payload["status_post"] = store.con.execute(
        "SELECT status FROM memory_items WHERE memory_id=?", (mid,)).fetchone()["status"]
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["asserts"], indent=1))


if __name__ == "__main__":
    main()
