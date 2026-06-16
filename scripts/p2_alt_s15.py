"""P2-alt — S15 partial(VP 学习批 + 组合 smoke;S10 NOT MEASURABLE 下仍可测)。"""
import importlib.util, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("sc", ROOT / "scripts" / "p2_stage_c.py")
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
from tachikoma.path_classifier import adoption_record
from tachikoma.resolver import check_segments
from tachikoma.store import MemoryStore

RESULTS = ROOT / "spikes" / "p2" / "alt_s15.json"
store = MemoryStore(sc.STORE)
payload = {"learning": [], "s15_runs": [], "asserts": {}}

# ---- VP 学习批(出生不依赖武装)----
for i, ref in enumerate(sc.LEARN, 1):
    print(f"[learn {i}/{len(sc.LEARN)}] {ref}", flush=True)
    r = sc.run_episode(store, ref, arm="memory_off", model=sc.MODEL, memory_on=False,
                       workspace_root=sc.WS / "alt_learn", learn=True)
    vp = sc._vp_row(store)
    payload["learning"].append({"variant_id": r["variant_id"], "eventual": r["eventual"],
                                "oracle": sc._oracle(store, r["episode_id"]),
                                "vp_after": dict(vp) if vp else None})
    print(f"    local={r['eventual']} vp={dict(vp) if vp else None}", flush=True)
    RESULTS.write_text(json.dumps(payload, indent=2))
    if vp and vp["status"].startswith("active"):
        print("VP 晋升,pass-early → 直接进 S15", flush=True)
        break

vp = sc._vp_row(store)
payload["asserts"]["vp_promoted"] = bool(vp and vp["status"].startswith("active"))
RESULTS.write_text(json.dumps(payload, indent=2))
if not payload["asserts"]["vp_promoted"]:
    print("VP 未晋升(学习批耗尽)——S15 partial 不可测,如实记录", flush=True)
    raise SystemExit(0)

# ---- S15 组合 smoke(4 run memory-on)----
mig = store.con.execute("SELECT memory_id FROM memory_items WHERE canonical_key"
                        " LIKE '%migrate%' AND status LIKE 'active%'").fetchone()["memory_id"]
refresh_ids = [r["memory_id"] for r in store.con.execute(
    "SELECT memory_id FROM memory_items WHERE canonical_key LIKE '%refresh%'")]
for i, ref in enumerate(["GH1@genb_v1", "GH4@genb_v1", "GH2@genb_v1", "GH5@genb_v1"], 1):
    print(f"[s15 {i}/4] {ref}", flush=True)
    r = sc.run_episode(store, ref, arm="memory_on", model=sc.MODEL, memory_on=True,
                       workspace_root=sc.WS / "alt_s15", learn=True)
    eid = r["episode_id"]
    ep, _, _ = store.episode_view(eid)
    vp_ad = any(a.kind in ("run", "test_run") and a.command
                and sc.CHECK_CMD in check_segments(a.command) for a in ep.actions)
    pd_ad = adoption_record(ep, "src/models.py", sc.MIGRATE_CMD).adopted
    rec = {"variant_id": r["variant_id"], "injected": r["injected"],
           "eventual": r["eventual"], "oracle": sc._oracle(store, eid),
           "vp_adopted": vp_ad, "pd_adopted": pd_ad,
           "retrieval_diag": sc._diag(store, eid)}
    payload["s15_runs"].append(rec)
    print(f"    inj={r['injected']} vp_ad={vp_ad} pd_ad={pd_ad}"
          f" diag={rec['retrieval_diag']}", flush=True)
    RESULTS.write_text(json.dumps(payload, indent=2))

both = [h for h in payload["s15_runs"] if len(h["injected"]) >= 2]
payload["asserts"]["s15"] = {
    "runs_with_both_types": len(both),
    "dual_adoption_runs": sum(1 for h in both if h["vp_adopted"] and h["pd_adopted"]),
    "pd_top1_is_migrate": all(mig in h["injected"] for h in both),
    "deprecated_refresh_never_injected": all(
        not (set(refresh_ids) & set(h["injected"])) for h in payload["s15_runs"]),
    "evaluable": len(both) >= 4}
RESULTS.write_text(json.dumps(payload, indent=2))
print(json.dumps(payload["asserts"], indent=1, ensure_ascii=False))
