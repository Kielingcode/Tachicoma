"""Retriever + PayloadRenderer (FR-33/FR-34, architecture §3.1).

确定性 trigger 过滤的输入只能是 workspace 文件列表与任务 prompt 文本——
本模块的任何接口都不接收 generator 的 family_id / fact_oracle(oracle 防火墙,FR-43;
行为级证明见 tests/test_retrieval.py)。候选集只读 status LIKE 'active%'(S3/P7)。
"""

from __future__ import annotations

import json
from pathlib import Path

_STATUS_RANK = {"active_verified": 0, "active_correlational": 1}


def retrieve(store, repo: str, workspace: Path, prompt: str, k: int = 3) -> list[dict]:
    """active* + repo scope + 确定性 trigger 过滤 → top-k(状态层级 > 证据量)。"""
    out = []
    for row in store.active_items(repo):
        trigger = json.loads(row["trigger_json"])
        path = trigger.get("after_edit", "")
        if not path:
            continue
        if _path_in_workspace(path, workspace) or path in prompt:
            out.append({
                "memory_id": row["memory_id"],
                "memory_type": row["memory_type"],
                "status": row["status"],
                "causal_verified": bool(row["causal_verified"]),
                "scope": json.loads(row["scope_json"]),
                "trigger": trigger,
                "action": json.loads(row["action_json"]),
                "support_count": row["support_count"],
                "contradiction_count": row["contradiction_count"],
                "distinct_task_family": row["distinct_task_family"],
            })
    out.sort(key=lambda m: (_STATUS_RANK.get(m["status"], 9), -m["support_count"]))
    return out[:k]


def _path_in_workspace(rel_path: str, workspace: Path) -> bool:
    return (Path(workspace) / rel_path).exists()


def render_payload(item: dict) -> str:
    """FR-34 memory payload(YAML 形态,逐字段)。"""
    caution = ("observed useful pattern, not yet causally verified"
               if not item["causal_verified"] else "causally verified via paired canary")
    instruction = (f"after editing {item['trigger'].get('after_edit')}, "
                   f"run \"{item['action'].get('must_run')}\" before final validation")
    return "\n".join([
        "memory_item:",
        f"  memory_id: {item['memory_id']}",
        f"  type: {item['memory_type']}",
        f"  status: {item['status']}",
        f"  causal_verified: {str(item['causal_verified']).lower()}",
        f"  scope: {json.dumps(item['scope'])}",
        f"  trigger: {json.dumps(item['trigger'])}",
        f"  instruction: {instruction}",
        f"  evidence: {{support_task_families: {item['distinct_task_family']}, "
        f"contradiction_count: {item['contradiction_count']}}}",
        f"  caution: {caution}",
    ])


def injection_block(items: list[dict]) -> str:
    if not items:
        return ""
    head = ("Relevant memory from previous tasks in this repository "
            "(governed memory; cite memory_id if you act on it):")
    return head + "\n\n" + "\n\n".join(render_payload(i) for i in items)
