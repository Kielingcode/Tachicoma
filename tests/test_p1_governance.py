"""P1 治理测试:G1 程序级负向、learning-excluded、dispute/deprecate 纯函数窗口、
rival top-1、CanaryEvaluator verified 重建(S4 延伸)。"""

import json

from tachicoma.canary import apply_verdict, evaluate, rebuild_verified
from tachicoma.store import MemoryStore


def _meta(eid, family, arm="memory_off", started="t0", success=1):
    return {"episode_id": eid, "task_id": f"t_{eid}", "family_id": family,
            "generator_template": "hidden_coupling_v4", "arm": arm, "repo": "orderkit",
            "model_version": "test", "agent_version": "test",
            "started_at": started, "ended_at": started, "first_try_success": 0,
            "eventual_success": success, "cost_steps": 6, "cost_tokens": 100,
            "wrong_turn_count": 0}


def _organic_events():
    return [
        {"step_idx": 1, "event_type": "FILE_EDIT", "payload": {"path": "src/models.py"}},
        {"step_idx": 2, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": False}},
        {"step_idx": 3, "event_type": "COMMAND_RUN",
         "payload": {"command": "python3 tools/refresh.py"}},
        {"step_idx": 4, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": True}},
    ]


def _g1_events(mid):
    """G1 关键轨迹:注入旧事实→采纳(refresh)→失败→换 migrate→最终恢复。"""
    return [
        {"step_idx": 0, "event_type": "MEMORY_INJECTED", "payload": {"memory_ids": [mid]}},
        {"step_idx": 1, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": False,
                     "source": "harness_pristine_check"}},
        {"step_idx": 2, "event_type": "FILE_EDIT", "payload": {"path": "src/models.py"}},
        {"step_idx": 3, "event_type": "COMMAND_RUN",
         "payload": {"command": "python3 tools/refresh.py"}},
        {"step_idx": 4, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": False}},
        {"step_idx": 5, "event_type": "COMMAND_RUN",
         "payload": {"command": "python3 tools/migrate.py"}},
        {"step_idx": 6, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": True}},
    ]


def _promoted_store():
    s = MemoryStore()
    s.ingest_episode(_meta("e1", "add-field", started="t1"), _organic_events())
    s.relearn("e1")
    s.ingest_episode(_meta("e2", "rename-field", started="t2"), _organic_events())
    s.relearn("e2")
    return s


def _mid(s):
    return s.con.execute("SELECT memory_id FROM memory_items WHERE canonical_key LIKE"
                         " '%refresh%'").fetchone()["memory_id"]


# ---------------------------------------------------------------- G1 ----

def test_g1_old_negative_new_positive_despite_eventual_recovery():
    """阻断级缺口修复:最终恢复不吞掉 stale harm——旧事实得负向,新事实得正向。"""
    s = _promoted_store()
    mid = _mid(s)
    meta = _meta("e3", "add-field", arm="memory_on", started="t3", success=1)  # 最终恢复!
    s.ingest_episode(meta, _g1_events(mid))
    s.relearn("e3")
    # 旧事实:程序级负向(采纳步后首测失败),即便 eventual_success=True
    neg = s.con.execute(
        "SELECT e.polarity, e.evidence_source FROM evidence_links e"
        " JOIN claims c ON e.claim_id=c.claim_id WHERE e.memory_id=? AND e.polarity<0",
        (mid,)).fetchall()
    assert len(neg) == 1 and neg[0]["evidence_source"] == "adoption_outcome"
    # 新事实(migrate):organic 正向 candidate(独立发现,非 adoption-conditioned)
    new = s.con.execute(
        "SELECT m.status, e.evidence_source FROM memory_items m"
        " JOIN evidence_links e ON m.memory_id=e.memory_id"
        " WHERE m.canonical_key LIKE '%migrate%'").fetchone()
    assert new is not None and new["status"] == "candidate"
    assert new["evidence_source"] == "organic_task"


# ------------------------------------------------- learning-excluded ----

def test_canary_arm_is_learning_excluded_at_store_level():
    s = _promoted_store()
    s.ingest_episode(_meta("c1", "add-field", arm="canary_with#p0", started="t3"),
                     _organic_events())
    r = s.relearn("c1")
    assert r.get("learning_excluded") is True
    assert s.con.execute(
        "SELECT COUNT(*) c FROM claims WHERE episode_id='c1'").fetchone()["c"] == 0


# ------------------------------------------- dispute / deprecate ----

def test_dispute_then_deprecate_window_is_pure_and_idempotent():
    """negatives≥2 → disputed(verified 同样适用);最近 M=3 无正向 → deprecated;
    双 relearn 重放零漂移(S4 延伸:降级路径)。"""
    s = _promoted_store()
    mid = _mid(s)
    for i, t in enumerate(("t3", "t4", "t5")):
        meta = _meta(f"n{i}", "add-field", arm="memory_on", started=t)
        s.ingest_episode(meta, _g1_events(mid))
        s.relearn(f"n{i}")
    status = s.con.execute(
        "SELECT status FROM memory_items WHERE memory_id=?", (mid,)).fetchone()["status"]
    assert status == "deprecated"   # 2 negatives → disputed;第 3 条后窗口无正向 → deprecated
    hist = [(_r["old_status"], _r["new_status"]) for _r in s.con.execute(
        "SELECT old_status,new_status FROM status_history WHERE memory_id=?"
        " ORDER BY id", (mid,))]
    assert ("active_correlational", "disputed") in hist
    assert ("disputed", "deprecated") in hist
    # 幂等重放(降级路径)
    before = {r["memory_id"]: r["status"] for r in
              s.con.execute("SELECT memory_id,status FROM memory_items")}
    for eid in ("e1", "e2", "n0", "n1", "n2"):
        s.relearn(eid)
    after = {r["memory_id"]: r["status"] for r in
             s.con.execute("SELECT memory_id,status FROM memory_items")}
    assert before == after


def test_observation_window_advances_under_suppression():
    """3b 实测修正:disputed 后被压制 → 零新证据 → 纯证据窗口冻结。
    同 repo 后续 learning-eligible episodes 的流逝 = "无回升"观察空槽;
    窗口推进后 deprecated 可达。重放幂等。"""
    s = _promoted_store()
    mid = _mid(s)
    # 2 个 G1 负向 episode;第二个的恢复翻转同时给旧 key 一条 adoption 正向
    # (复刻 3a 实况:[neg, neg, pos] → 纯证据窗口永含正向)
    s.ingest_episode(_meta("n0", "add-field", arm="memory_on", started="t3"),
                     _g1_events(mid))
    s.relearn("n0")
    recovery = _g1_events(mid) + [
        {"step_idx": 7, "event_type": "FILE_EDIT", "payload": {"path": "src/models.py"}},
        {"step_idx": 8, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": False}},
        {"step_idx": 9, "event_type": "COMMAND_RUN",
         "payload": {"command": "python3 tools/refresh.py"}},
        {"step_idx": 10, "event_type": "TEST_RUN",
         "payload": {"command": "python3 -m pytest tests/ -q", "passed": True}},
    ]
    s.ingest_episode(_meta("n1", "add-field", arm="memory_on", started="t4"), recovery)
    s.relearn("n1")
    assert s.con.execute("SELECT status FROM memory_items WHERE memory_id=?",
                         (mid,)).fetchone()["status"] == "disputed"
    # 3 个与旧 key 无关的 episodes 流逝(migrate 路线)→ 窗口推进 → deprecated
    def mig_events():
        ev = _organic_events()
        ev[2] = {"step_idx": 3, "event_type": "COMMAND_RUN",
                 "payload": {"command": "python3 tools/migrate.py"}}
        return ev
    for i, t in enumerate(("t5", "t6", "t7")):
        s.ingest_episode(_meta(f"m{i}", "add-field", arm="memory_on", started=t),
                         mig_events())
        s.relearn(f"m{i}")
    assert s.con.execute("SELECT status FROM memory_items WHERE memory_id=?",
                         (mid,)).fetchone()["status"] == "deprecated"
    # 重放零漂移(含 sweep 路径)
    before = {r["memory_id"]: r["status"] for r in
              s.con.execute("SELECT memory_id,status FROM memory_items")}
    for eid in ("e1", "e2", "n0", "n1", "m0", "m1", "m2"):
        s.relearn(eid)
    after = {r["memory_id"]: r["status"] for r in
             s.con.execute("SELECT memory_id,status FROM memory_items")}
    assert before == after


def test_deprecated_is_suppressed_from_retrieval():
    s = _promoted_store()
    mid = _mid(s)
    for i, t in enumerate(("t3", "t4", "t5")):
        s.ingest_episode(_meta(f"n{i}", "add-field", arm="memory_on", started=t),
                         _g1_events(mid))
        s.relearn(f"n{i}")
    assert all(r["memory_id"] != mid for r in s.active_items("orderkit"))


# ---------------------------------------------------------- rival ----

def test_rival_top1_with_suppression_logged():
    from pathlib import Path

    from tachicoma.retrieval import retrieve
    s = _promoted_store()           # refresh 事实 active
    # 同 trigger、不同 action 的第二个事实(migrate)也推到 active
    def mig_events():
        ev = _organic_events()
        ev[2] = {"step_idx": 3, "event_type": "COMMAND_RUN",
                 "payload": {"command": "python3 tools/migrate.py"}}
        return ev
    s.ingest_episode(_meta("m1", "add-field", started="t3"), mig_events())
    s.relearn("m1")
    s.ingest_episode(_meta("m2", "rename-field", started="t4"), mig_events())
    s.relearn("m2")
    import tempfile
    ws = Path(tempfile.mkdtemp())
    (ws / "src").mkdir()
    (ws / "src" / "models.py").write_text("# f", encoding="utf-8")
    winners, suppressed, _diag = retrieve(s, "orderkit", ws, "Add a field", k=5)
    assert len(winners) == 1            # 同 rival_key 只注入 top-1
    assert len(suppressed) == 1
    assert winners[0]["memory_id"] != suppressed[0]["memory_id"]


def test_inert_pruning_after_k_unadopted_injections():
    """FR-25/S13:最近 K=3 次注入连续未采纳 → deprecated(直接弧);
    被采纳即重置(adoption_support 抵抗);重放幂等。"""
    s = _promoted_store()
    mid = _mid(s)

    def unadopted_events():
        # 注入但 agent 走自己的路(无 refresh 运行)→ adopted=False
        return [
            {"step_idx": 0, "event_type": "MEMORY_INJECTED",
             "payload": {"memory_ids": [mid]}},
            {"step_idx": 1, "event_type": "TEST_RUN",
             "payload": {"command": "python3 -m pytest tests/ -q", "passed": False,
                         "source": "harness_pristine_check"}},
            {"step_idx": 2, "event_type": "FILE_EDIT", "payload": {"path": "src/models.py"}},
            {"step_idx": 3, "event_type": "TEST_RUN",
             "payload": {"command": "python3 -m pytest tests/ -q", "passed": True}},
        ]

    for i, t in enumerate(("t3", "t4")):
        s.ingest_episode(_meta(f"u{i}", "add-field", arm="memory_on", started=t),
                         unadopted_events())
        s.relearn(f"u{i}")
    # 2 次未采纳:未到 K=3,仍 active
    assert s.con.execute("SELECT status FROM memory_items WHERE memory_id=?",
                         (mid,)).fetchone()["status"] == "active_correlational"
    s.ingest_episode(_meta("u2", "add-field", arm="memory_on", started="t5"),
                     unadopted_events())
    s.relearn("u2")
    assert s.con.execute("SELECT status FROM memory_items WHERE memory_id=?",
                         (mid,)).fetchone()["status"] == "deprecated"
    hist = s.con.execute(
        "SELECT reason FROM status_history WHERE memory_id=? ORDER BY id DESC LIMIT 1",
        (mid,)).fetchone()["reason"]
    assert "inert" in hist
    # 重放零漂移
    before = {r["memory_id"]: r["status"] for r in
              s.con.execute("SELECT memory_id,status FROM memory_items")}
    for eid in ("e1", "e2", "u0", "u1", "u2"):
        s.relearn(eid)
    after = {r["memory_id"]: r["status"] for r in
             s.con.execute("SELECT memory_id,status FROM memory_items")}
    assert before == after


def test_adoption_resets_inert_streak():
    """采纳 = 抵抗信号:2 未采纳 + 1 采纳 + 2 未采纳 → 最近 3 次含采纳,不剪。"""
    s = _promoted_store()
    mid = _mid(s)

    def injected(events_passed_via_refresh):
        ev = [{"step_idx": 0, "event_type": "MEMORY_INJECTED",
               "payload": {"memory_ids": [mid]}},
              {"step_idx": 1, "event_type": "TEST_RUN",
               "payload": {"command": "python3 -m pytest tests/ -q", "passed": False,
                           "source": "harness_pristine_check"}},
              {"step_idx": 2, "event_type": "FILE_EDIT",
               "payload": {"path": "src/models.py"}}]
        if events_passed_via_refresh:
            ev.append({"step_idx": 3, "event_type": "COMMAND_RUN",
                       "payload": {"command": "python3 tools/refresh.py"}})
        ev.append({"step_idx": 4, "event_type": "TEST_RUN",
                   "payload": {"command": "python3 -m pytest tests/ -q", "passed": True}})
        return ev

    for i, (t, adopt) in enumerate(zip(("t3", "t4", "t5", "t6", "t7"),
                                       (False, False, True, False, False))):
        s.ingest_episode(_meta(f"u{i}", "add-field", arm="memory_on", started=t),
                         injected(adopt))
        s.relearn(f"u{i}")
    status = s.con.execute("SELECT status FROM memory_items WHERE memory_id=?",
                           (mid,)).fetchone()["status"]
    assert status.startswith("active")   # 最近 3 = [True, False, False] → 不剪


# ------------------------------------------ CanaryEvaluator(S4 延伸)----

def _canary_pair(s, pid, *, with_steps, without_steps, mid, started):
    s.ingest_episode(_meta(f"cw{pid}", "add-field", arm=f"canary_with#p{pid}",
                           started=started, success=1) | {"cost_steps": with_steps,
                                                          "episode_id": f"cw{pid}"},
                     [{"step_idx": 0, "event_type": "MEMORY_INJECTED",
                       "payload": {"memory_ids": [mid]}}] + _organic_events())
    s.ingest_episode(_meta(f"co{pid}", "add-field", arm=f"canary_without#p{pid}",
                           started=started, success=1) | {"cost_steps": without_steps,
                                                          "episode_id": f"co{pid}"},
                     _organic_events())


def test_canary_evaluate_apply_and_rebuild_verified():
    s = _promoted_store()
    mid = _mid(s)
    for pid, (w, wo) in enumerate([(8, 15), (9, 16), (8, 14)]):
        _canary_pair(s, pid, with_steps=w, without_steps=wo, mid=mid, started=f"t{3+pid}")
    v = evaluate(s, mid, step_delta_gate=4, theta_adopt=0.8)
    assert v["accept"] and v["median_step_delta"] == 7 and v["adoption_rate"] == 1.0
    assert apply_verdict(s, v) is True
    row = s.con.execute("SELECT status, causal_verified FROM memory_items"
                        " WHERE memory_id=?", (mid,)).fetchone()
    assert row["status"] == "active_verified" and row["causal_verified"] == 1
    # S4 延伸:人为清零 → 纯函数重建恢复(P16 无例外)
    s.con.execute("UPDATE memory_items SET causal_verified=0,"
                  " status='active_correlational' WHERE memory_id=?", (mid,))
    s.con.commit()
    rebuild_verified(s, mid, step_delta_gate=4, theta_adopt=0.8)
    row = s.con.execute("SELECT status, causal_verified FROM memory_items"
                        " WHERE memory_id=?", (mid,)).fetchone()
    assert row["status"] == "active_verified" and row["causal_verified"] == 1
    # 幂等:再 apply 一次为 no-op
    assert apply_verdict(s, evaluate(s, mid, step_delta_gate=4, theta_adopt=0.8)) is False


def test_verified_is_not_a_death_exemption():
    """G-3:verified + 程序级负向 ≥2 → disputed(非免死金牌)。"""
    s = _promoted_store()
    mid = _mid(s)
    for pid, (w, wo) in enumerate([(8, 15), (9, 16), (8, 14)]):
        _canary_pair(s, pid, with_steps=w, without_steps=wo, mid=mid, started=f"t{3+pid}")
    apply_verdict(s, evaluate(s, mid, step_delta_gate=4, theta_adopt=0.8))
    for i, t in enumerate(("t9", "t10")):
        s.ingest_episode(_meta(f"n{i}", "add-field", arm="memory_on", started=t),
                         _g1_events(mid))
        s.relearn(f"n{i}")
    status = s.con.execute("SELECT status FROM memory_items WHERE memory_id=?",
                           (mid,)).fetchone()["status"]
    assert status == "disputed"
