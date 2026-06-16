"""P2 Stage B1 round-2 — genb rev2(无运行时自检)基线重测(回炉协议)。"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "b1", ROOT / "scripts" / "p2_b1_calibration.py")
b1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b1)

from tachikoma.store import MemoryStore  # noqa: E402

RESULTS = ROOT / "spikes" / "p2" / "b1_calibration.json"


def main() -> None:
    store = MemoryStore(b1.STORE)
    payload = json.loads(RESULTS.read_text())
    payload["genb_r2"] = []
    b1.RESULTS = RESULTS

    def batch():
        for i, ref in enumerate(b1.GENB_SIDE, 1):
            print(f"[genb-r2 {i}/6] {ref}", flush=True)
            r = b1.run_episode(store, ref, arm="diagnostic_calib_genb2",
                               model=b1.MODEL, memory_on=False,
                               workspace_root=b1.WS / "r2", learn=False)
            p = b1._profile(r, store)
            payload["genb_r2"].append(p)
            print(f"    local={p['eventual_local']} oracle={p['oracle_passed']}"
                  f" false_success={p['false_success']} steps={p['cost_steps']}"
                  f" bypass={p['bypass']}", flush=True)
            RESULTS.write_text(json.dumps(payload, indent=2))

    batch()
    fs = sum(1 for p in payload["genb_r2"] if p["false_success"])
    if fs == 2:
        print("== ambiguous 2/6 → 补 4 run ==", flush=True)
        for i, ref in enumerate(b1.GENB_SUPP, 1):
            print(f"[genb-r2-supp {i}/4] {ref}", flush=True)
            r = b1.run_episode(store, ref, arm="diagnostic_calib_genb2",
                               model=b1.MODEL, memory_on=False,
                               workspace_root=b1.WS / "r2s", learn=False)
            p = b1._profile(r, store)
            payload["genb_r2"].append(p)
            RESULTS.write_text(json.dumps(payload, indent=2))
        fs = sum(1 for p in payload["genb_r2"] if p["false_success"])
        n = len(payload["genb_r2"])
        verdict = (f"ARMED ({fs}/{n} ≥ 4/10)" if fs >= 4
                   else f"NOT ARMED round2 ({fs}/{n}) → S10 NOT MEASURABLE → P2-alt")
    elif fs >= 3:
        verdict = f"ARMED round2 ({fs}/6)"
    else:
        verdict = f"NOT ARMED round2 ({fs}/6 ≤ 1/6) → S10 NOT MEASURABLE → P2-alt(G2)"
    payload["gate_r2"] = {"genb_false_success_r2": f"{fs}/{len(payload['genb_r2'])}",
                          "verdict": verdict,
                          "fixture_rev": "genb_v1-rev2(types.py 无运行时自检)"}
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["gate_r2"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
