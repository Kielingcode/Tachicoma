"""OracleEvaluator — FR-43,eval-only。

防火墙(模块边界强制):governance / extractor / retrieval / store 不得 import 本模块;
本模块只读 store,永不写。oracle key 由调用方(demo/calibrate 等 eval 侧驱动)从
TaskBundle.fact_oracle 派生后传入——learning path 看不到它。
"""

from __future__ import annotations

import json

from tachikoma.resolver import canonical_key


def oracle_key(fact_oracle: dict) -> str:
    return canonical_key("ProceduralDependency",
                         {"after_edit": fact_oracle["after_edit"]},
                         {"must_run": fact_oracle["must_run"]})


def fact_precision(store, oracle_keys: set[str]) -> dict:
    """extracted 正向 claims / promoted items 与 oracle 的吻合度。"""
    pos = store.con.execute(
        "SELECT canonical_key FROM claims WHERE polarity>0").fetchall()
    promoted = store.con.execute(
        "SELECT canonical_key FROM memory_items WHERE status LIKE 'active%'").fetchall()
    return {
        "claim_precision": _ratio([r["canonical_key"] in oracle_keys for r in pos]),
        "promoted_precision": _ratio([r["canonical_key"] in oracle_keys for r in promoted]),
        "n_positive_claims": len(pos),
        "n_promoted": len(promoted),
    }


def injection_precision(store, episode_oracle: dict[str, str]) -> dict:
    """每次 MEMORY_INJECTED:注入 memory 的 canonical_key 是否匹配该任务的 oracle key。"""
    hits, total = 0, 0
    rows = store.con.execute(
        "SELECT episode_id, payload_json FROM raw_events"
        " WHERE event_type='MEMORY_INJECTED'").fetchall()
    for r in rows:
        want = episode_oracle.get(r["episode_id"])
        if want is None:
            continue
        for mid in json.loads(r["payload_json"]).get("memory_ids", []):
            item = store.con.execute(
                "SELECT canonical_key FROM memory_items WHERE memory_id=?", (mid,)).fetchone()
            total += 1
            hits += int(bool(item) and item["canonical_key"] == want)
    return {"injection_precision": (hits / total) if total else None, "n_injections": total}


def _ratio(flags: list[bool]) -> float | None:
    return (sum(flags) / len(flags)) if flags else None
