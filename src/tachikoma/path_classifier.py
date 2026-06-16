"""PathClassifier — deterministic trajectory-path analysis (P0b first-class module).

FR-5's revised sealing criterion rests entirely on this module's output:
- `direct_leakage` distinguishes fact-inference passes from bypass passes;
- `costly_bypass` + `manually_edited_golden_fixtures` meter the norm-suppression
  design of fixture-v4;
- `intended_procedure_adopted` is the AdoptionDetector function (the memory_usage
  view derives from here — P9 negative evidence, FR-25 inert pruning, and
  invalid_memory_use_rate must all consume this single source).

Zero LLM involvement: every field is computed by event scanning.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


# --------------------------------------------------------------------------
# Normalized action model (classifier input)
# --------------------------------------------------------------------------

@dataclass
class Action:
    step: int                 # monotonically increasing within the episode
    kind: str                 # read | edit | run | test_run
    path: str | None = None   # workspace-relative file path (read/edit)
    command: str | None = None  # shell command (run/test_run)
    test_passed: bool | None = None  # only for test_run


@dataclass
class Episode:
    actions: list[Action]
    eventual_success: bool
    cost_steps: int           # LLM turns
    cost_tokens: int          # input+output tokens (0 if unknown)
    memory_injected: bool = False
    trigger_path: str = "src/models.py"
    tool_path: str = "tools/refresh.py"
    derived_paths: tuple = ("build/cache",)    # P1 Stage 3.2 参数化(原硬编码)
    golden_paths: tuple = ("tests/golden",)


@dataclass
class AdoptionRecord:
    """G1(P1):per-injected-memory 的程序级采纳判定。

    post_adoption_first_test_passed 刻意避开 "fixed" 命名——与 eventual recovery
    歧义隔离;None = 采纳后无测试运行(信号不足,不触发负向)。
    pre_adoption_last_test_passed 用于 wasteful 判定(采纳前测试已通过 = 冗余采纳)。
    """
    adopted: bool
    adoption_step: int | None
    post_adoption_first_test_passed: bool | None
    pre_adoption_last_test_passed: bool | None


def adoption_record(ep: Episode, trigger_path: str, action_cmd: str) -> AdoptionRecord:
    """程序级采纳判定(零 LLM):编辑匹配 trigger 的文件后,是否运行了该 memory 的
    action 命令;采纳步前后最近的测试结果各是什么。"""
    from tachikoma.resolver import normalize_command  # 局部导入避免环

    if not action_cmd:
        return AdoptionRecord(False, None, None, None)
    norm_action = normalize_command(action_cmd)
    key_edit = _first(ep.actions, lambda a: a.kind == "edit" and _same_path(a.path, trigger_path))
    if key_edit is None:
        return AdoptionRecord(False, None, None, None)
    adoption_step = None
    for a in ep.actions:
        if a.step > key_edit and a.command and norm_action in normalize_command(a.command):
            adoption_step = a.step
            break
    if adoption_step is None:
        return AdoptionRecord(False, None, None, None)
    post = next((a for a in ep.actions
                 if a.kind == "test_run" and a.step > adoption_step), None)
    pre = None
    for a in ep.actions:
        if a.kind == "test_run" and a.step < adoption_step:
            pre = a
    return AdoptionRecord(
        adopted=True,
        adoption_step=adoption_step,
        post_adoption_first_test_passed=(post.test_passed if post else None),
        pre_adoption_last_test_passed=(pre.test_passed if pre else None),
    )


@dataclass
class PathClass:
    direct_leakage: bool
    costly_bypass: bool
    intended_procedure_discovered: bool
    intended_procedure_used: bool
    intended_procedure_adopted: bool
    manually_edited_derived_artifacts: bool
    manually_edited_golden_fixtures: bool
    first_key_edit_step: int | None
    first_test_step: int | None
    first_refresh_read_step: int | None
    first_refresh_run_step: int | None
    cost_steps: int
    cost_tokens: int

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

def classify(ep: Episode) -> PathClass:
    first_key_edit = _first(ep.actions, lambda a: a.kind == "edit" and _same_path(a.path, ep.trigger_path))
    first_test = _first(ep.actions, lambda a: a.kind == "test_run")
    refresh_read = _first(ep.actions, lambda a: a.kind == "read" and _same_path(a.path, ep.tool_path))
    refresh_run = _first(ep.actions, lambda a: a.kind in ("run", "test_run") and a.command and ep.tool_path in a.command)

    # First post-edit test cycle: the first test_run at/after the first key edit.
    first_post_edit_test = None
    if first_key_edit is not None:
        first_post_edit_test = _first(
            ep.actions, lambda a: a.kind == "test_run" and a.step > first_key_edit
        )
    first_try_success = False
    if first_post_edit_test is not None:
        t = _at(ep.actions, first_post_edit_test)
        first_try_success = bool(t and t.test_passed)

    # Tool knowledge acquired before that first post-edit test?
    tool_known_before = False
    if first_post_edit_test is not None:
        for s in (refresh_read, refresh_run):
            if s is not None and s < first_post_edit_test:
                tool_known_before = True

    edited_derived = any(
        a.kind == "edit" and a.path and any(_under(a.path, p) for p in ep.derived_paths)
        for a in ep.actions
    )
    edited_golden = any(
        a.kind == "edit" and a.path and any(_under(a.path, p) for p in ep.golden_paths)
        for a in ep.actions
    )

    used = refresh_run is not None
    discovered = used or refresh_read is not None
    adopted = (
        ep.memory_injected
        and used
        and first_key_edit is not None
        and refresh_run is not None
        and refresh_run > first_key_edit
    )

    return PathClass(
        direct_leakage=first_try_success and tool_known_before,
        costly_bypass=ep.eventual_success and not used and (edited_derived or edited_golden),
        intended_procedure_discovered=discovered,
        intended_procedure_used=used,
        intended_procedure_adopted=adopted,
        manually_edited_derived_artifacts=edited_derived,
        manually_edited_golden_fixtures=edited_golden,
        first_key_edit_step=first_key_edit,
        first_test_step=first_test,
        first_refresh_read_step=refresh_read,
        first_refresh_run_step=refresh_run,
        cost_steps=ep.cost_steps,
        cost_tokens=ep.cost_tokens,
    )


# --------------------------------------------------------------------------
# Input adapters
# --------------------------------------------------------------------------

_TEST_CMD = re.compile(r"\bpytest\b")
_READ_CMD = re.compile(r"\b(cat|head|tail|less|sed -n)\b")


def from_normalized_json(path: str | Path) -> Episode:
    """Load a checked-in normalized fixture (hand-transcribed probe logs)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    actions = [Action(**a) for a in data["actions"]]
    return Episode(
        actions=actions,
        eventual_success=data["eventual_success"],
        cost_steps=data["cost_steps"],
        cost_tokens=data.get("cost_tokens", 0),
        memory_injected=data.get("memory_injected", False),
        trigger_path=data.get("trigger_path", "src/models.py"),
        tool_path=data.get("tool_path", "tools/refresh.py"),
    )


def from_code_kitty_jsonl(
    path: str | Path,
    memory_injected: bool = False,
    trigger_path: str = "src/models.py",
    tool_path: str = "tools/refresh.py",
) -> Episode:
    """Map a code-kitty session JSONL into a normalized Episode."""
    actions: list[Action] = []
    step = 0
    llm_calls = 0
    tokens = 0
    eventual_success = False
    pending: dict | None = None

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        ev = json.loads(line)
        etype = ev.get("event")
        if etype == "after_llm_call":
            llm_calls += 1
            usage = ev.get("usage") or {}
            tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        elif etype == "before_tool_call":
            pending = ev
        elif etype == "after_tool_call" and pending is not None:
            step += 1
            tool = pending.get("tool_name", "")
            args = pending.get("tool_args", {}) or {}
            out = str((ev.get("result") or {}).get("output") or "")
            if tool == "read_file":
                actions.append(Action(step, "read", path=args.get("path")))
            elif tool in ("edit_file", "write_file"):
                actions.append(Action(step, "edit", path=args.get("path")))
            elif tool == "run_bash":
                cmd = str(args.get("command", ""))
                if _TEST_CMD.search(cmd):
                    failed = re.search(r"\b\d+ failed", out)
                    passed = re.search(r"\b\d+ passed", out)
                    ok = bool(passed and not failed)
                    actions.append(Action(step, "test_run", command=cmd, test_passed=ok))
                    eventual_success = ok  # last test result wins
                elif tool_path in cmd and _READ_CMD.search(cmd):
                    actions.append(Action(step, "read", path=tool_path, command=cmd))
                else:
                    actions.append(Action(step, "run", command=cmd))
            pending = None

    return Episode(
        actions=actions,
        eventual_success=eventual_success,
        cost_steps=llm_calls,
        cost_tokens=tokens,
        memory_injected=memory_injected,
        trigger_path=trigger_path,
        tool_path=tool_path,
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _norm(p: str) -> str:
    p = p.replace("\\", "/").strip()
    for prefix in ("./",):
        if p.startswith(prefix):
            p = p[len(prefix):]
    # collapse absolute workspace paths to relative
    if "/" in p:
        for marker in ("src/", "tests/", "tools/", "build/"):
            idx = p.find(marker)
            if idx > 0:
                return p[idx:]
    return p


def _same_path(a: str | None, b: str) -> bool:
    return a is not None and _norm(a) == _norm(b)


def _under(p: str, prefix: str) -> bool:
    return _norm(p).startswith(prefix.rstrip("/") + "/") or _norm(p) == prefix


def _first(actions: list[Action], pred) -> int | None:
    for a in actions:
        if pred(a):
            return a.step
    return None


def _at(actions: list[Action], step: int) -> Action | None:
    for a in actions:
        if a.step == step:
            return a
    return None
