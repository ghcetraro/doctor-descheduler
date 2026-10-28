from app.appearance import normalize_theme


def test_normalize_theme() -> None:
    assert normalize_theme("light") == "light"
    assert normalize_theme(" LIGHT ") == "light"
    assert normalize_theme("dark") == "dark"
    assert normalize_theme("") == "dark"
    assert normalize_theme(None) == "dark"
