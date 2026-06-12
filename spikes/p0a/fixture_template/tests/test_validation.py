from src.lib.validation import clamp, is_email, require_keys


def test_email():
    assert is_email("a@b.co")
    assert not is_email("nope")


def test_clamp():
    assert clamp(15, 0, 10) == 10


def test_require_keys():
    assert require_keys({"a": 1}, ["a", "b"]) == ["b"]
