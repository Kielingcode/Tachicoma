from src.lib.money import apply_percentage, cents_to_display, split_even


def test_display():
    assert cents_to_display(1250) == "$12.50"
    assert cents_to_display(-5) == "-$0.05"


def test_percentage():
    assert apply_percentage(1000, 7.5) == 75


def test_split_even():
    assert split_even(100, 3) == [34, 33, 33]
