"""P1 Stage 3b 补完(2 run)+ 观察期语义修正后的全量重放验收。

背景(P1_LOG 详):3b 前 2 run 在 remedy 指引加入前被 bypass 烧掉,其后 SEG 内
只剩 add-field → migrate 困在 candidate(fam=1)。补:R3@rot_v2b(rename)促晋升;
NM3@rot_v2b 验证 rival top-1 归位。随后全量 relearn 重放:
(a) 新观察期语义下旧 memory disputed → deprecated(窗口可推进);
(b) S4 零漂移(重放幂等,降级路径含观察期 sweep)。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tachicoma.runner import run_episode
from tachicoma.store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "spikes" / "p1"
STORE = OUT_DIR / "verified.sqlite"
RESULTS = OUT_DIR / "rot_supplement.json"
WS = Path("/tmp/p1_runs/rot/3b")
MODEL = "claude-sonnet-4-6"


def _row(store, like):
    return store.con.execute(
        "SELECT memory_id, status FROM memory_items WHERE canonical_key LIKE ?",
        (like,)).fetchone()


def main() -> None:
    store = MemoryStore(STORE)
    old = _row(store, "%refresh%")
    payload = {"runs": [], "asserts": {}}

    print("[supp 1/2] R3@rot_v2b (rename → fam≥2)", flush=True)
    r = run_episode(store, "R3@rot_v2b", arm="rot3b", model=MODEL, memory_on=True,
                    workspace_root=WS, learn=True)
    payload["runs"].append({k: r[k] for k in ("episode_id", "variant_id", "injected",
                                              "eventual", "cost_steps")})
    mig = _row(store, "%migrate%")
    print(f"    eventual={r['eventual']} migrate={dict(mig) if mig else None}"
          f" old={_row(store, '%refresh%')['status']}", flush=True)

    print("[supp 2/2] NM3@rot_v2b (top-1 归位验证)", flush=True)
    r2 = run_episode(store, "NM3@rot_v2b", arm="rot3b", model=MODEL, memory_on=True,
                     workspace_root=WS, learn=True)
    payload["runs"].append({k: r2[k] for k in ("episode_id", "variant_id", "injected",
                                               "eventual", "cost_steps")})
    mig = _row(store, "%migrate%")
    old_now = _row(store, "%refresh%")
    payload["asserts"]["migrate_promoted"] = bool(
        mig and mig["status"] == "active_correlational")
    payload["asserts"]["top1_is_migrate_only"] = bool(
        mig and r2["injected"] == [mig["memory_id"]])
    payload["asserts"]["old_deprecated_live"] = old_now["status"] == "deprecated"

    # 全量重放(P16/S4):episodes 即事实源,重放后状态不漂移
    before = {r_["memory_id"]: r_["status"] for r_ in
              store.con.execute("SELECT memory_id, status FROM memory_items")}
    eids = [r_["episode_id"] for r_ in store.con.execute(
        "SELECT episode_id FROM episodes ORDER BY started_at")]
    for eid in eids:
        store.relearn(eid)
    after = {r_["memory_id"]: r_["status"] for r_ in
             store.con.execute("SELECT memory_id, status FROM memory_items")}
    payload["asserts"]["replay_zero_drift"] = before == after
    payload["asserts"]["old_deprecated_after_replay"] = (
        _row(store, "%refresh%")["status"] == "deprecated")
    payload["final"] = {"old": dict(_row(store, "%refresh%")),
                        "migrate": dict(_row(store, "%migrate%"))}
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["asserts"], indent=1))


if __name__ == "__main__":
    main()
