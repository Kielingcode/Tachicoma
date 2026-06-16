"""PathClassifier 对 P0a 真实标注轨迹的分类必须与人工标注一致(plan Stage 2)。"""

from pathlib import Path

import pytest

from tachikoma.path_classifier import classify, from_code_kitty_jsonl, from_normalized_json

FIXTURES = Path(__file__).parent / "fixtures"


def test_seal_06_is_direct_leakage():
    pc = classify(from_normalized_json(FIXTURES / "seal_06_direct_leakage.json"))
    assert pc.direct_leakage is True
    assert pc.costly_bypass is False
    assert pc.intended_procedure_discovered is True
    assert pc.intended_procedure_used is True
    assert pc.first_refresh_read_step == 8
    assert pc.first_key_edit_step == 9


def test_seal_11_is_intended_procedure():
    pc = classify(from_normalized_json(FIXTURES / "seal_11_intended.json"))
    assert pc.direct_leakage is False          # 首个 edit→test 失败,工具知识在失败之后获得
    assert pc.costly_bypass is False
    assert pc.intended_procedure_used is True
    assert pc.manually_edited_derived_artifacts is False
    assert pc.first_refresh_read_step == 8
    assert pc.first_refresh_run_step == 9


def test_seal_13_is_costly_bypass():
    pc = classify(from_normalized_json(FIXTURES / "seal_13_costly_bypass.json"))
    assert pc.direct_leakage is False
    assert pc.costly_bypass is True
    assert pc.intended_procedure_discovered is False   # 从未读/运行 refresh
    assert pc.intended_procedure_used is False
    assert pc.manually_edited_derived_artifacts is True
    assert pc.manually_edited_golden_fixtures is False  # v3 时代还没有 golden


def test_real_code_kitty_session_adoption():
    """ck_a2_mem(P0a 真实 memory-on 会话):注入后采纳了 refresh.py。"""
    jsonl = FIXTURES / "ck_a2_mem.jsonl"
    if not jsonl.exists():
        pytest.skip("real session fixture not present")
    ep = from_code_kitty_jsonl(jsonl, memory_injected=True)
    pc = classify(ep)
    assert pc.intended_procedure_used is True
    assert pc.intended_procedure_adopted is True
    assert pc.cost_steps == 10
    assert pc.cost_tokens > 0
    assert ep.eventual_success is True


def test_real_code_kitty_session_bypass():
    """ck_a2_nomem(P0a 真实 memory-off 会话):旁路,从未用工具。"""
    jsonl = FIXTURES / "ck_a2_nomem.jsonl"
    if not jsonl.exists():
        pytest.skip("real session fixture not present")
    pc = classify(from_code_kitty_jsonl(jsonl))
    assert pc.intended_procedure_used is False
    assert pc.costly_bypass is True
    assert pc.manually_edited_derived_artifacts is True
