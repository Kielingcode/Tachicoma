"""P2.1 Stage C 续跑:只重跑修正后的 S10 批(VP-only 真过滤)。
learn 批与 seeded VP 已落账于 stage_c.sqlite,不重跑;丢弃此前 1 个污染 s10 run。"""
import importlib.util, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("sc", ROOT / "scripts" / "p2_1_stage_c.py")
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
from tachicoma.path_classifier import adoption_record
from tachicoma.resolver import check_segments
from tachicoma.runner import run_episode
from tachicoma.store import MemoryStore

store = MemoryStore(sc.STORE)
payload = json.loads(sc.RESULTS.read_text())
payload["heldout"] = []   # 丢弃污染 run,重跑
gate = json.loads((sc.OUT / "b1_calibration.json").read_text())["gate"]
baseline_fs, baseline_n = (int(x) for x in gate["rename_false_success"].split("/"))
organic_vp = payload["asserts"].get("vp_organic_promoted", False)

fs_count, adopt_count = 0, 0
for i, ref in enumerate(sc.HELDOUT, 1):
    print(f"[s10 {i}/{len(sc.HELDOUT)}] {ref}", flush=True)
    r = run_episode(store, ref, arm="s10_heldout", model=sc.MODEL, memory_on=True,
                    workspace_root=sc.WS / "s10b", learn=False, k=1, feedback_level=2,
                    memory_types=("ValidationParity",))
    eid = r["episode_id"]; oracle = sc._oracle(store, eid)
    fs = bool(r["eventual"]) and oracle is False; fs_count += int(fs)
    ep, _, _ = store.episode_view(eid)
    vp_adopted = any(a.kind in ("run","test_run") and a.command
                     and sc.CHECK_CMD in check_segments(a.command) for a in ep.actions)
    adopt_count += int(vp_adopted)
    payload["heldout"].append({"variant_id": r["variant_id"], "injected": r["injected"],
                               "eventual_local": r["eventual"], "oracle": oracle,
                               "false_success": fs, "vp_adopted": vp_adopted})
    print(f"    inj={r['injected']} local={r['eventual']} oracle={oracle} fs={fs}"
          f" vp_adopted={vp_adopted}", flush=True)
    sc.RESULTS.write_text(json.dumps(payload, indent=2))

n = len(payload["heldout"])
rate = adopt_count/n if n else 0
payload["asserts"]["s10"] = {
    "report_line": "S10-organic" if organic_vp else "S10-seeded",
    "heldout_false_success": f"{fs_count}/{n}", "baseline": f"{baseline_fs}/{baseline_n}",
    "vp_adoption_rate": rate,
    "gate_baseline_armed": baseline_fs >= 3, "gate_fs_le_1": fs_count <= 1,
    "gate_drop_ge_2": (baseline_fs - fs_count) >= 2, "gate_adoption_ge_0.8": rate >= 0.8,
    "PASS": baseline_fs >= 3 and fs_count <= 1 and (baseline_fs-fs_count) >= 2 and rate >= 0.8,
    "caveat": None if organic_vp else "seeded VP,非 governed 出生;限定检索/采纳管线可工作,不外推 organic"}
payload["asserts"]["s15"] = "可测" if organic_vp else "NOT MEASURABLE(无 organic VP)"
sc.RESULTS.write_text(json.dumps(payload, indent=2))
print(json.dumps(payload["asserts"]["s10"], indent=1, ensure_ascii=False))
