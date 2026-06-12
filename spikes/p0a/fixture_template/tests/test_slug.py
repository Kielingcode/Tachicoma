from src.lib.slug import slugify, unique_slug


def test_slugify():
    assert slugify("Hello, World!") == "hello-world"


def test_unique():
    assert unique_slug("a", {"a", "a-2"}) == "a-3"
