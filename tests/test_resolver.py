"""归一化规则(norm-v2)单测——每条规则对应一次实测裂缝。"""

from tachikoma.resolver import canonical_key, normalize_command


def test_interpreter_folding_and_paths():
    assert normalize_command("python tools/refresh.py") == "python3 tools/refresh.py"
    assert normalize_command("/Users/x/ws/y && python3 /Users/x/ws/tools/refresh.py") \
        .endswith("python3 tools/refresh.py")


def test_redirection_stripping_norm_v2():
    # P0b Stage 6 实测裂缝:`2>&1` 让同一 fact 碎成两个 canonical key
    assert normalize_command("python3 tools/refresh.py 2>&1") == "python3 tools/refresh.py"
    assert normalize_command("python3 tools/refresh.py > /tmp/out.txt") == \
        "python3 tools/refresh.py"
    assert normalize_command("python3 tools/refresh.py 2>/dev/null") == \
        "python3 tools/refresh.py"
    assert normalize_command("python3 tools/refresh.py >> run.log 2>&1") == \
        "python3 tools/refresh.py"


def test_canonical_key_identity_across_noise():
    a = canonical_key("ProceduralDependency", {"after_edit": "./src/models.py"},
                      {"must_run": "python tools/refresh.py 2>&1"})
    b = canonical_key("ProceduralDependency", {"after_edit": "src/models.py"},
                      {"must_run": "python3  tools/refresh.py"})
    assert a == b == "ProceduralDependency|src/models.py|python3 tools/refresh.py"
