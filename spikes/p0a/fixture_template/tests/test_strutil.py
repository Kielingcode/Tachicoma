from src.lib.strutil import collapse_ws, initials, truncate


def test_truncate():
    assert truncate("hello world", 8) == "hello..."
    assert truncate("short", 10) == "short"


def test_collapse_ws():
    assert collapse_ws("a   b\t c") == "a b c"


def test_initials():
    assert initials("ada lovelace") == "AL"
