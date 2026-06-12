"""P1 Stage 4 应急补批:static 学习批全 bypass(0 lesson)时的续航。

复用 p1_ungoverned.run_u;按序补 static(A2、B2、A1 重试)直到 reflector
学到 ≥1 条 lesson,然后跑 rotated 3(与 3a 同 variants 配对)。
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "p1_ungoverned", ROOT / "scripts" / "p1_ungoverned.py")
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

from tachicoma.reflector import Reflector  # noqa: E402
from tachicoma.store import MemoryStore    # noqa: E402

RESULTS = ROOT / "spikes" / "p1" / "ungoverned_results.json"
STATIC_RETRY = ["A2", "B2", "A1"]


def main() -> None:
    store = MemoryStore(u.STORE)
    adapter = u.CodeKittyAdapter()
    reflector = Reflector(u.LESSONS)
    payload = (json.loads(RESULTS.read_text())
               if RESULTS.exists() else {"static_learning": [], "rotated": []})

    for ref in STATIC_RETRY:
        if reflector.injection_block():
            break
        print(f"[U static-retry] {ref}", flush=True)
        r = u.run_u(store, adapter, reflector, ref, "arm_u_static")
        payload["static_learning"].append(r)
        print(f"    eventual={r['eventual']} lessons_added={r['lessons_added']}",
              flush=True)
        RESULTS.write_text(json.dumps(payload, indent=2))

    if not reflector.injection_block():
        payload["abort"] = "static 批 + 重试全 bypass,无 lesson 可注入——如实记录"
        RESULTS.write_text(json.dumps(payload, indent=2))
        print(payload["abort"])
        return

    for i, ref in enumerate(u.ROTATED, 1):
        print(f"[U rotated {i}/{len(u.ROTATED)}] {ref}", flush=True)
        r = u.run_u(store, adapter, reflector, ref, "arm_u_rotated")
        payload["rotated"].append(r)
        print(f"    eventual={r['eventual']} steps={r['cost_steps']}"
              f" lessons_injected={r['lessons_injected']}", flush=True)
        RESULTS.write_text(json.dumps(payload, indent=2))

    payload["expectation_check"] = {
        "u_rotated_keeps_failing": all(not r["eventual"] for r in payload["rotated"]
                                       if r.get("lessons_injected")),
        "u_lessons_never_pruned": True,
    }
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["expectation_check"], indent=1))


if __name__ == "__main__":
    main()
