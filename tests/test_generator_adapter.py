"""Generator 物化 + adapter 映射的结构性测试(不触 API)。"""

from pathlib import Path

from tachikoma.adapter import session_to_raw_events
from tachikoma.generator import (HELDOUT_VARIANTS, LEARNING_VARIANTS, NORM_LINE,
                                 VARIANTS, materialize)
from tachikoma.path_classifier import Episode, classify
from tachikoma.runner import events_to_actions

FIXTURES = Path(__file__).parent / "fixtures"


def test_variant_registry_families_and_disjointness():
    fams = {VARIANTS[v]["family_id"] for v in LEARNING_VARIANTS}
    assert fams == {"add-field", "rename-field"}          # 晋升门的两个 family
    assert {VARIANTS[v]["family_id"] for v in HELDOUT_VARIANTS} == \
        {"add-field", "rename-field", "change-type"}
    # learning 与 held-out 的 (family, prompt) 参数不相交
    lp = {VARIANTS[v]["prompt"] for v in LEARNING_VARIANTS}
    hp = {VARIANTS[v]["prompt"] for v in HELDOUT_VARIANTS}
    assert not lp & hp


def test_materialize_overlay_and_norm(tmp_path):
    b = materialize("H4", tmp_path / "ws")
    assert b.family_id == "change-type"
    assert NORM_LINE in b.prompt
    assert (tmp_path / "ws" / "tools" / "refresh.py").exists()
    assert not list((tmp_path / "ws").rglob("__pycache__"))
    records = (tmp_path / "ws" / "tests" / "test_records.py").read_text(encoding="utf-8")
    assert "total=12.5" in records and "total_cents" not in records


def test_materialize_add_field_variant(tmp_path):
    b = materialize("H1", tmp_path / "ws")
    t = (tmp_path / "ws" / "tests" / "test_variant.py").read_text(encoding="utf-8")
    assert 'reference="PO-77"' in t and b.family_id == "add-field"


def test_adapter_mapping_consistent_with_classifier():
    """adapter 的 JSONL→raw_events 与 PathClassifier 语义一致(ck_a2_mem=adopted)。"""
    res = session_to_raw_events(FIXTURES / "ck_a2_mem.jsonl")
    assert res.cost_steps > 0 and res.cost_tokens > 0
    assert res.agent_version and res.model_version
    ep = Episode(actions=events_to_actions(res.events), eventual_success=True,
                 cost_steps=res.cost_steps, cost_tokens=res.cost_tokens,
                 memory_injected=True)
    pc = classify(ep)
    assert pc.intended_procedure_used and pc.intended_procedure_adopted
    assert not pc.costly_bypass
