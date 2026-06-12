"""Governance — derived belief + the P0 counting promotion gate (FR-19/FR-23).

P0 gate (satisfiability-checked):  families >= 2  AND  S >= 2  AND  S >= 3F  AND actionable.
Preponderance instead of zero-veto: one flaky contradiction does not block promotion;
sustained contradiction does. Beta posterior machinery activates at P1 with calibrated θ.
The generator's fact_oracle must never appear here (FR-43 firewall — this module
must not import tachicoma.oracle_eval).
"""

from __future__ import annotations


def recompute_belief(cur, memory_id: str) -> dict:
    """Full recompute from evidence_links + episodes (never incremental — P4/P16).

    Evidence-class boundary(P0b 裁决):
    - independent_support / families:只数 evidence_source='organic_task' 的正向
      (memory-off 独立发现)——这是 birth/promotion 的唯一燃料;
    - adoption_support:memory-on adopted+success 的正向,单独累计
      (utility / demotion 抵抗用,P1 裁决权重);
    - contradiction:负向无论来源全计(P9 不对称性:注入后仍失败是可信负信号)。
    """
    import json as _json

    rows = cur.execute(
        "SELECT e.polarity, e.evidence_source, ep.family_id FROM evidence_links e"
        " JOIN claims c ON e.claim_id=c.claim_id"
        " JOIN episodes ep ON c.episode_id=ep.episode_id"
        " WHERE e.memory_id=?", (memory_id,)).fetchall()
    support = sum(1 for r in rows
                  if r["polarity"] > 0 and r["evidence_source"] == "organic_task")
    adoption = sum(1 for r in rows
                   if r["polarity"] > 0 and r["evidence_source"] == "adoption_outcome")
    contra = sum(1 for r in rows if r["polarity"] < 0)
    families = len({r["family_id"] for r in rows
                    if r["polarity"] > 0 and r["evidence_source"] == "organic_task"
                    and r["family_id"]})
    belief = {"support": support, "contra": contra, "families": families,
              "adoption_support": adoption}
    cur.execute(
        "INSERT INTO belief_states (memory_id, support_count, contradiction_count,"
        " distinct_task_family, per_context_json, computed_from_version,"
        " first_seen, last_seen)"
        " VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))"
        " ON CONFLICT(memory_id) DO UPDATE SET support_count=excluded.support_count,"
        " contradiction_count=excluded.contradiction_count,"
        " distinct_task_family=excluded.distinct_task_family,"
        " per_context_json=excluded.per_context_json,"
        " computed_from_version=excluded.computed_from_version,"
        " last_seen=datetime('now')",
        (memory_id, support, contra, families,
         _json.dumps({"adoption_support": adoption}), "gate-v2"))
    return belief


def evaluate_gate(current_status: str, belief: dict) -> str:
    """Counting rule. Cascade-aware: items that no longer satisfy the gate demote."""
    s, f, fam = belief["support"], belief["contra"], belief["families"]
    qualifies = fam >= 2 and s >= 2 and s >= 3 * f
    if current_status == "candidate" and qualifies:
        return "active_correlational"
    if current_status == "active_correlational" and not qualifies:
        return "candidate"   # demote on evidence loss (relearn cascade, FR-18)
    return current_status
