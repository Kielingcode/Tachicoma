"""P2.1 Stage D-core — S13b placebo 复测(指引效用 vs 程序效用)。

回测 P2 的 S13b 结论:P2 用 program 臂(注入真程序记忆)vs without 臂测出
median delta 6,判低效用降级。但"被注入权威指令本身减少探索"(指引效用)会混淆。
本段加 **placebo 臂**(同 trigger、中性指令,无 load-bearing 程序),三臂配对:
  program  = 注入 refresh 程序记忆(P1 wasteful 的候选)
  placebo  = 注入"请仔细确认本任务步骤"中性指令(同 trigger,零程序内容)
  without  = 不注入
操作性判定(n≈4,不谈显著):
  program_median_delta − placebo_median_delta ≤ STEP_GATE(6) → 指引效用混淆成立;
  > STEP_GATE → 支持程序效用。
canary 用显式 episode-id 集隔离(防 Stage D 污染重演)。store 血统:P1 wasteful 副本。
"""

import json
import shutil
import statistics
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tachicoma.runner import run_episode
from tachicoma.store import MemoryStore

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spikes" / "p2_1"
SRC = ROOT / "spikes" / "p1" / "wasteful.sqlite"
STORE = OUT / "s13b_placebo.sqlite"
RESULTS = OUT / "stage_d.json"
WS = Path("/tmp/p2_1_runs/d")
MODEL = "claude-sonnet-4-6"
STEP_GATE = 6
PLACEBO_TEXT = ("Relevant note for this repository: take care to confirm each step "
                "of the task before finishing.")   # 同 trigger 语境、零 load-bearing 程序
PAIRS = ["W1@shim_v1", "W2@shim_v1", "W3@shim_v1"]


def _steps(store, eid):
    return store.con.execute("SELECT cost_steps FROM episodes WHERE episode_id=?",
                             (eid,)).fetchone()["cost_steps"]


def main() -> None:
    if not STORE.exists():
        shutil.copy(SRC, STORE)
    store = MemoryStore(STORE)
    refresh = store.con.execute("SELECT memory_id FROM memory_items"
                                " WHERE canonical_key LIKE '%refresh%'").fetchone()["memory_id"]
    payload = {"candidate": refresh, "triples": [], "verdict": {}}
    prog_d, plac_d = [], []

    for i, ref in enumerate(PAIRS):
        print(f"[triple {i}] {ref}", flush=True)
        # program:注入真 refresh 记忆
        w = run_episode(store, ref, arm=f"canary_with#p{i}", model=MODEL, memory_on=True,
                        workspace_root=WS, learn=False)
        # placebo:同 trigger 中性指令(memory_off + 文案前缀,经 adapter 注入 block)
        wo = run_episode(store, ref, arm=f"canary_without#p{i}", model=MODEL,
                         memory_on=False, workspace_root=WS, learn=False)
        pl = run_episode(store, ref, arm=f"canary_placebo#p{i}", model=MODEL,
                         memory_on=False, workspace_root=WS, learn=False,
                         adapter=_PlaceboAdapter())
        ws, wos, pls = _steps(store, w["episode_id"]), _steps(store, wo["episode_id"]), \
            _steps(store, pl["episode_id"])
        prog_d.append(wos - ws)
        plac_d.append(wos - pls)
        payload["triples"].append({"variant": ref, "program": ws, "placebo": pls,
                                   "without": wos, "program_delta": wos - ws,
                                   "placebo_delta": wos - pls})
        print(f"    program={ws} placebo={pls} without={wos}"
              f" → prog_delta={wos-ws} plac_delta={wos-pls}", flush=True)
        RESULTS.write_text(json.dumps(payload, indent=2))

    prog_med = statistics.median(prog_d)
    plac_med = statistics.median(plac_d)
    diff = prog_med - plac_med
    payload["verdict"] = {
        "program_median_delta": prog_med, "placebo_median_delta": plac_med,
        "diff": diff, "step_gate": STEP_GATE,
        "guidance_confound": diff <= STEP_GATE,
        "interpretation": (
            "指引效用混淆成立:S13b 降级部分测的是指引衰减(program≈placebo)"
            if diff <= STEP_GATE else
            "支持程序效用:program 显著高于 placebo(程序本身有用)"),
        "note": "diagnostic,n=3,不做统计显著性声明",
    }
    RESULTS.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["verdict"], indent=1, ensure_ascii=False))


class _PlaceboAdapter:
    """memory_off 但 prompt 前缀注入中性指令——隔离"被告知权威信息"的指引效用。"""
    def __init__(self):
        from tachicoma.adapter import CodeKittyAdapter
        self._inner = CodeKittyAdapter()

    def run(self, task, workspace, model, injection_block="", **kw):
        return self._inner.run(task, workspace, model,
                               injection_block=PLACEBO_TEXT, **kw)


if __name__ == "__main__":
    main()
