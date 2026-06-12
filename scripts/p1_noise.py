"""P1 Stage 1 — 噪声地板 f(FR-30/A5)。

协议(plan v1.3):H1(add-field held-out)+ H3(rename held-out)×
{memory-off k=3, memory-on k=1} = 8 run。目的 = 保守噪声边界,非精确分布。
arm="noise", learn=False(且 Stage 2 起 store.relearn 按 arm 排除——双层保险)。
"""

import json
import shutil
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tachicoma.runner import run_episode
from tachicoma.store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "spikes" / "p1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SRC_STORE = ROOT / "spikes" / "p0b" / "demo" / "arm_b.sqlite"
NOISE_STORE = OUT_DIR / "noise.sqlite"

MODEL = "claude-sonnet-4-6"
PLAN = [("H1", False), ("H1", False), ("H1", False), ("H1", True),
        ("H3", False), ("H3", False), ("H3", False), ("H3", True)]


def main() -> None:
    shutil.copy(SRC_STORE, NOISE_STORE)
    store = MemoryStore(NOISE_STORE)
    results = []
    for i, (vid, mem_on) in enumerate(PLAN, 1):
        print(f"[{i}/{len(PLAN)}] {vid} memory_on={mem_on}", flush=True)
        r = run_episode(store, vid, arm="noise", model=MODEL, memory_on=mem_on,
                        workspace_root=Path("/tmp/p1_runs/noise"), learn=False)
        results.append({k: r[k] for k in
                        ("episode_id", "variant_id", "memory_on", "first_try",
                         "eventual", "cost_steps", "cost_tokens")})
        print(f"    eventual={r['eventual']} steps={r['cost_steps']}", flush=True)

    report = {"runs": results}
    for vid in ("H1", "H3"):
        off = [r for r in results if r["variant_id"] == vid and not r["memory_on"]]
        outcomes = [r["eventual"] for r in off]
        steps = sorted(r["cost_steps"] for r in off)
        flips = sum(1 for o in outcomes if o != max(set(outcomes), key=outcomes.count))
        report[vid] = {
            "off_outcomes": outcomes, "off_steps": steps,
            "f_outcome": flips / len(outcomes),
            "steps_range": steps[-1] - steps[0],
        }
    all_off_steps = sorted(r["cost_steps"] for r in results if not r["memory_on"])
    n = len(all_off_steps)
    iqr = all_off_steps[3 * n // 4] - all_off_steps[n // 4]
    report["f_steps_iqr_off_pooled"] = iqr
    report["suggested_thresholds"] = {
        "step_delta_gate": max(2 * iqr, 2),
        "note": "step-delta 门 > 2×IQR(plan Stage 1);翻转门 > f_outcome",
    }
    (OUT_DIR / "noise_floor.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "runs"}, indent=1))


if __name__ == "__main__":
    main()
