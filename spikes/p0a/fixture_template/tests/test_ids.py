from src.lib.ids import is_valid_id, normalize_id


def test_valid():
    assert is_valid_id("o-12ab", "o")
    assert not is_valid_id("x-12ab", "o")


def test_normalize():
    assert normalize_id("  O_12AB ".lower()) == "o-12ab"
