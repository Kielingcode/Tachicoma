"""P2.2 efficacy 隔离 — genb_hs feedback-OFF 对照(~6 run)。

C1(on 臂,6 run genb_hs rename)已得 2 VP 出生。本批同世界、同 6 个 rename 变体、
**feedback_level=None(off)**,比较 off 臂的 VP 出生率 / 探索率。
- off 出生显著低于 on(2/6)→ 反馈是出生的活性成分(efficacy PASS);
- off 出生 ≈ on → 出生由世界结构(逼先错)驱动,反馈贡献≈0(efficacy = 世界,非反馈);
- 逐 run 同 C1 的分环诊断(①-⑤,⑥重标)。
独立 store(不污染 C1);不种反馈(off 臂本就不用反馈)。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tachicoma.resolver import check_segments
from tachicoma.runner import run_episode
from tachicoma.store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spikes" / "p2_2"
STORE = OUT / "efficacy_off.sqlite"
RESULTS = OUT / "efficacy.json"
WS = Path("/tmp/p2_2_runs/eff")
MODEL = "claude-sonnet-4-6"
CHECK_CMD = "python3 tools/check_contract.py"

ARMED = ["GR2@genb_hs", "GR4@genb_hs", "GR5@genb_hs", "GR6@genb_hs",
         "GR7@genb_hs", "GR9@genb_hs"]


def _classify(store, eid):
    ep, _, _ = store.episode_view(eid)
    cr = [a for a in ep.actions if a.kind in ("run", "test_run") and a.command
          and CHECK_CMD in check_segments(a.command)]
    read_tools = any(a.kind == "read" and (a.path or "").startswith("tools/") for a in ep.actions)
    ran = len(cr) > 0
    seen_fail = flip = False
    for a in cr:
        if a.test_passed is False:
            seen_fail = True
        elif a.test_passed and seen_fail:
            flip = True
    saw_fail = any(a.test_passed is False for a in cr)
    oracle = next((a.test_passed for a in ep.actions if a.kind == "oracle_check"), None)
    vp = store.con.execute(
        "SELECT COUNT(*) c FROM claims WHERE episode_id=? AND claim_type='ValidationParity'"
        " AND polarity>0", (eid,)).fetchone()["c"]
    if vp >= 1 and oracle:
        st = "5_vp_born"
    elif ran and not saw_fail and oracle:
        st = "6_correct_first_try"
    elif oracle is False and ran:
        st = "4_fixed_oracle_still_red"
    elif ran and saw_fail and not flip:
        st = "3_ran_saw_fail_didnt_fix"
    elif read_tools and not ran:
        st = "2_explored_not_run"
    else:
        st = "1_not_explored"
    return st, {"ran_check": ran, "check_flip": flip, "oracle": oracle, "vp_minted": vp}


def main():
    store = MemoryStore(STORE)
    payload = {"runs": [], "verdict": {}}
    for i, ref in enumerate(ARMED, 1):
        print(f"[off {i}/6] {ref}", flush=True)
        r = run_episode(store, ref, arm="genb_hs_vp_off", model=MODEL, memory_on=False,
                        workspace_root=WS, learn=True, feedback_level=None)   # OFF
        st, sig = _classify(store, r["episode_id"])
        payload["runs"].append({"variant": ref, "stage": st, **sig})
        print(f"    stage={st} ran_check={sig['ran_check']} flip={sig['check_flip']}"
              f" oracle={sig['oracle']} vp={sig['vp_minted']}", flush=True)
        RESULTS.write_text(json.dumps(payload, indent=2))

    from collections import Counter
    dist = Counter(r["stage"] for r in payload["runs"])
    off_births = sum(r["vp_minted"] for r in payload["runs"])
    off_explored = sum(1 for r in payload["runs"] if r["ran_check"])
    # on 臂(C1)对照
    c1 = json.loads((OUT / "stage_c.json").read_text())
    on_births = sum(r["vp_minted"] for r in c1["runs"])
    on_explored = sum(1 for r in c1["runs"] if r["ran_check"])
    payload["verdict"] = {
        "on_births": on_births, "off_births": off_births,
        "on_ran_check": on_explored, "off_ran_check": off_explored,
        "off_stage_dist": dict(dist),
        "efficacy": (
            "PASS:反馈是出生活性成分(off 出生显著低于 on)" if off_births < on_births else
            "= 世界结构非反馈(off 出生 ≈/≥ on,逼先错才是活性成分)"),
    }
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["verdict"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
