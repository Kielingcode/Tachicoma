"""P1 Stage 3b 收尾:补第二 family 的 migrate 证据 → 晋升 → top-1 归位验证。

实测行为:rename 任务两次诱发 bypass(手同步三件套)。按序尝试
NM4(rename)→ H4(change-type,手同步成本更高);migrate 晋升后跑
NM1@rot_v2b 验证检索注入恰为 [migrate](S7 杀旧立新的注入侧证据)。
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
RESULTS = OUT_DIR / "rot_promote.json"
WS = Path("/tmp/p1_runs/rot/3b")
MODEL = "claude-sonnet-4-6"

FAMILY_CANDIDATES = ["NM4@rot_v2b", "H4@rot_v2b"]


def _mig(store):
    return store.con.execute(
        "SELECT memory_id, status FROM memory_items"
        " WHERE canonical_key LIKE '%migrate%'").fetchone()


def main() -> None:
    store = MemoryStore(STORE)
    payload = {"runs": [], "asserts": {}}

    for ref in FAMILY_CANDIDATES:
        mig = _mig(store)
        if mig and mig["status"].startswith("active"):
            break
        print(f"[promote] {ref}", flush=True)
        r = run_episode(store, ref, arm="rot3b", model=MODEL, memory_on=True,
                        workspace_root=WS, learn=True)
        payload["runs"].append({k: r[k] for k in ("episode_id", "variant_id", "injected",
                                                  "eventual", "cost_steps", "path_class")})
        mig = _mig(store)
        print(f"    eventual={r['eventual']} migrate={dict(mig) if mig else None}",
              flush=True)
        RESULTS.write_text(json.dumps(payload, indent=2))

    mig = _mig(store)
    payload["asserts"]["migrate_promoted"] = bool(
        mig and mig["status"] == "active_correlational")

    if payload["asserts"]["migrate_promoted"]:
        print("[verify] NM1@rot_v2b(top-1 注入)", flush=True)
        r = run_episode(store, "NM1@rot_v2b", arm="rot3b", model=MODEL, memory_on=True,
                        workspace_root=WS, learn=True)
        payload["runs"].append({k: r[k] for k in ("episode_id", "variant_id", "injected",
                                                  "eventual", "cost_steps")})
        payload["asserts"]["top1_is_migrate_only"] = r["injected"] == [mig["memory_id"]]
        print(f"    injected={r['injected']} eventual={r['eventual']}", flush=True)

    old = store.con.execute("SELECT status FROM memory_items"
                            " WHERE canonical_key LIKE '%refresh%'").fetchone()
    payload["asserts"]["old_still_deprecated"] = old["status"] == "deprecated"
    payload["final_migrate"] = dict(_mig(store))
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["asserts"], indent=1))


if __name__ == "__main__":
    main()
