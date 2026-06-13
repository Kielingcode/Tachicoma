"""P2.2 Stage B — FR-8b delivery 验证(配对,~8 run,genb_v1)。

4 feedback_on(level=2)+ 4 feedback_off,同世界同批交错。种子:批首植入一条
同族(orderkit/rename-field)oracle-fail,作标注 raw_event 落账(seeded=true),
使 on 臂从首 run 起就有反馈可用。
读数:(c) 主交付 replay-faithful 真实-run 回归;(b) organic VP 出生(genb_v1≈恒0);
(a) on/off 探索增量(diagnostic)。出口:delivery PASS | 送达失败回炉。
**B 只测 delivery,不测 efficacy**(efficacy 在 Stage C 的 genb_hs 测)。
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tachicoma.feedback import reconstruct_shown_feedback
from tachicoma.resolver import check_segments
from tachicoma.runner import run_episode
from tachicoma.store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spikes" / "p2_2"
STORE = OUT / "stage_b.sqlite"
RESULTS = OUT / "stage_b.json"
WS = Path("/tmp/p2_2_runs/b")
MODEL = "claude-sonnet-4-6"
CHECK_CMD = "python3 tools/check_contract.py"

# 8 武装 rename 变体(genb_v1;Stage B 用 genb_v1 测 delivery)
PAIRS = ["GR2", "GR4", "GR5", "GR6", "GR7", "GR8", "GR9", "GR11"]
# 交错:on/off/on/off...
ARMS = [(v, 2 if i % 2 == 0 else None) for i, v in enumerate(PAIRS)]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _seed(store):
    """植入种子 oracle-fail(orderkit/rename-field),标注 seeded raw_event 落账。"""
    eid = f"seed-{uuid.uuid4().hex[:6]}"
    store.ingest_episode({
        "episode_id": eid, "task_id": "seed", "family_id": "rename-field",
        "generator_template": "genb_v1", "arm": "diagnostic_seed", "repo": "orderkit",
        "model_version": "seed", "agent_version": "seed",
        "started_at": "2020-01-01T00:00:00", "ended_at": "2020-01-01T00:00:00",
        "first_try_success": 0, "eventual_success": 1, "cost_steps": 0,
        "cost_tokens": 0, "wrong_turn_count": 0,
    }, [{"step_idx": 1, "event_type": "DELAYED_CHECK_RESULT",
         "payload": {"passed": False, "source": "seeded", "seeded": True}}])
    print(f"seeded oracle-fail episode {eid} (orderkit/rename-field) landed", flush=True)


def _oracle(store, eid):
    r = store.con.execute("SELECT payload_json FROM raw_events WHERE episode_id=?"
                          " AND event_type='DELAYED_CHECK_RESULT'"
                          " AND json_extract(payload_json,'$.source')='harness_hidden_oracle'",
                          (eid,)).fetchone()
    return json.loads(r["payload_json"]).get("passed") if r else None


def _explored(store, eid):
    for r in store.con.execute("SELECT event_type, payload_json FROM raw_events"
                               " WHERE episode_id=?", (eid,)):
        p = json.loads(r["payload_json"])
        if "check_" in (p.get("command") or "") or "tools/" in (p.get("command") or "") \
                or (p.get("path") or "").startswith("tools/"):
            return True
    return False


def _vp_count(store):
    return store.con.execute("SELECT COUNT(*) c FROM memory_items"
                             " WHERE memory_type='ValidationParity'").fetchone()["c"]


def main():
    store = MemoryStore(STORE)
    _seed(store)
    payload = {"runs": [], "delivery": {}, "diagnostics": {}}

    for i, (vid, lvl) in enumerate(ARMS, 1):
        on = lvl is not None
        print(f"[{i}/8] {vid} feedback={'ON' if on else 'OFF'}", flush=True)
        r = run_episode(store, f"{vid}@genb_v1", arm="diagnostic_delivery", model=MODEL,
                        memory_on=False, workspace_root=WS, learn=True, feedback_level=lvl)
        eid = r["episode_id"]
        # (c) delivery 验收(仅 on 臂期望有反馈事件)
        rec = reconstruct_shown_feedback(store, eid)
        explored = _explored(store, eid)
        rec_ok = (rec is not None) if on else (rec is None)
        payload["runs"].append({
            "variant": vid, "feedback_on": on,
            "feedback_landed": rec is not None,
            "feedback_text_recovered": rec["text"] if rec else None,
            "delivery_ok": rec_ok, "explored": explored,
            "oracle": _oracle(store, eid), "cost_steps": r["cost_steps"]})
        print(f"    feedback_landed={rec is not None} delivery_ok={rec_ok}"
              f" explored={explored} oracle={_oracle(store, eid)}", flush=True)
        RESULTS.write_text(json.dumps(payload, indent=2))

    # (c) replay-faithful:全量 relearn 重放零漂移
    before = {r["memory_id"]: r["status"] for r in
              store.con.execute("SELECT memory_id,status FROM memory_items")}
    for r in store.con.execute("SELECT episode_id FROM episodes ORDER BY started_at").fetchall():
        store.relearn(r["episode_id"])
    after = {r["memory_id"]: r["status"] for r in
             store.con.execute("SELECT memory_id,status FROM memory_items")}

    on_runs = [r for r in payload["runs"] if r["feedback_on"]]
    off_runs = [r for r in payload["runs"] if not r["feedback_on"]]
    payload["delivery"] = {
        "all_on_landed": all(r["feedback_landed"] for r in on_runs),
        "all_off_no_feedback": all(not r["feedback_landed"] for r in off_runs),
        "all_delivery_ok": all(r["delivery_ok"] for r in payload["runs"]),
        "replay_zero_drift": before == after,
        "PASS": (all(r["delivery_ok"] for r in payload["runs"]) and before == after),
    }
    payload["diagnostics"] = {
        "vp_organic_births": _vp_count(store),   # genb_v1 期望 ≈ 0(死分支探针)
        "explore_on": sum(r["explored"] for r in on_runs),
        "explore_off": sum(r["explored"] for r in off_runs),
        "note": "(a) on/off 探索增量 = diagnostic only(天花板绑定);(b) VP 出生 genb_v1≈恒0",
    }
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"delivery": payload["delivery"],
                      "diagnostics": payload["diagnostics"]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
