"""S3(只注入 active)+ oracle 防火墙行为级证明(plan v1.1 Stage 5 修订 5)。"""

import inspect

from tachikoma.retrieval import injection_block, render_payload, retrieve
from tachikoma.store import MemoryStore


def _events(cmd="python3 tools/refresh.py"):
    return [
        {"step_idx": 1, "event_type": "FILE_EDIT", "payload": {"path": "src/models.py"}},
        {"step_idx": 2, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": False}},
        {"step_idx": 3, "event_type": "COMMAND_RUN", "payload": {"command": cmd}},
        {"step_idx": 4, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": True}},
    ]


def _meta(eid, family, repo="orderkit"):
    return {"episode_id": eid, "task_id": f"t_{eid}", "family_id": family,
            "generator_template": "hidden_coupling", "arm": "memory_off", "repo": repo,
            "model_version": "test", "agent_version": "test",
            "started_at": "", "ended_at": "", "first_try_success": 0,
            "eventual_success": 1, "cost_steps": 4, "cost_tokens": 100,
            "wrong_turn_count": 0}


def _store_with_active_and_candidate():
    s = MemoryStore()
    # active:两 family 支持同一 fact
    s.ingest_episode(_meta("e1", "add-field"), _events())
    s.relearn("e1")
    s.ingest_episode(_meta("e2", "rename-field"), _events())
    s.relearn("e2")
    # candidate:单 family 的另一条 fact(不同 action 槽)
    s.ingest_episode(_meta("e3", "add-field"), _events(cmd="python3 tools/fmt.py"))
    s.relearn("e3")
    return s


def test_s3_only_active_injected(tmp_path):
    s = _store_with_active_and_candidate()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "models.py").write_text("# fixture", encoding="utf-8")
    items, _sup, _d = retrieve(s, "orderkit", tmp_path, "Add a field to the Customer model", k=5)
    assert len(items) == 1
    assert items[0]["status"] == "active_correlational"
    payload = render_payload(items[0])
    assert "memory_id:" in payload and "not yet causally verified" in payload
    assert items[0]["memory_id"] in injection_block(items)


def test_retrieval_does_not_use_generator_family_id(tmp_path):
    """防火墙(FR-43/architecture §3.1):trigger 过滤的输入只有 workspace 与 prompt。"""
    # 签名级:retrieve 根本不接收 family_id / bundle / oracle
    # memory_types 是 fact-type 受控过滤(P2.1 VP-only 隔离),非 generator 元数据,
    # 不引入防火墙泄漏面——纳入白名单。
    params = set(inspect.signature(retrieve).parameters)
    assert params == {"store", "repo", "workspace", "prompt", "k", "memory_types"}

    s = _store_with_active_and_candidate()

    # scope 匹配 ∧ family 不匹配(change-type,从未学过)∧ trigger 文件匹配 → 注入 ✓
    ws = tmp_path / "w1"
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "models.py").write_text("# fixture", encoding="utf-8")
    hit, _, _d2 = retrieve(s, "orderkit", ws, "Change the Invoice model to store float dollars")
    assert [i["memory_id"] for i in hit], "novel family must still be injected on trigger match"

    # family 匹配(add-field,学习时见过)∧ trigger 不匹配(无文件、prompt 不提)→ 不注入 ✓
    ws2 = tmp_path / "w2"
    ws2.mkdir()
    miss, _, _d3 = retrieve(s, "orderkit", ws2, "Add a retry helper to the http client")
    assert miss == []


def test_scope_filter_blocks_other_repo(tmp_path):
    s = _store_with_active_and_candidate()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "models.py").write_text("# fixture", encoding="utf-8")
    assert retrieve(s, "another-repo", tmp_path, "Add a field to Customer")[0] == []
