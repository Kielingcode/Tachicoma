"""B1 round-2 续跑(GB5/GB6,GB5 原跑被挂死杀掉,未入库)。"""
import importlib.util, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("b1", ROOT / "scripts" / "p2_b1_calibration.py")
b1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b1)
from tachicoma.store import MemoryStore
RESULTS = ROOT / "spikes" / "p2" / "b1_calibration.json"
store = MemoryStore(b1.STORE)
payload = json.loads(RESULTS.read_text())
for ref in ("GB5@genb_v1", "GB6@genb_v1"):
    print(f"[resume] {ref}", flush=True)
    r = b1.run_episode(store, ref, arm="diagnostic_calib_genb2", model=b1.MODEL,
                       memory_on=False, workspace_root=b1.WS / "r2", learn=False)
    p = b1._profile(r, store)
    payload["genb_r2"].append(p)
    print(f"    local={p['eventual_local']} oracle={p['oracle_passed']}"
          f" fs={p['false_success']} steps={p['cost_steps']} bypass={p['bypass']}", flush=True)
    RESULTS.write_text(json.dumps(payload, indent=2))
fs = sum(1 for p in payload["genb_r2"] if p["false_success"])
n = len(payload["genb_r2"])
verdict = (f"ARMED round2 ({fs}/{n})" if fs >= 3 else
           f"ambiguous ({fs}/{n})" if fs == 2 else
           f"NOT ARMED round2 ({fs}/{n} ≤ 1/6) → S10 NOT MEASURABLE → P2-alt(G2)")
payload["gate_r2"] = {"genb_false_success_r2": f"{fs}/{n}", "verdict": verdict,
                      "fixture_rev": "genb_v1-rev2(types.py 无运行时自检)"}
RESULTS.write_text(json.dumps(payload, indent=2))
print(json.dumps(payload["gate_r2"], indent=1, ensure_ascii=False))
