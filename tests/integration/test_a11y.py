from pathlib import Path


def test_client_html_accessibility_structure():
    index_html_path = Path("client/index.html")
    assert index_html_path.exists()
    content = index_html_path.read_text(encoding="utf-8")

    # Check semantic landmarks
    assert "<main" in content
    assert "<form" in content
    assert 'aria-live="polite"' in content
    assert 'role="alert"' in content

    # Check labeled controls
    assert "<label" in content
    assert "for=" in content
    assert "<input" in content
    assert "<button" in content


def test_client_css_contrast_and_focus():
    css_path = Path("client/style.css")
    assert css_path.exists()
    content = css_path.read_text(encoding="utf-8")

    # Focus indicator check
    assert ":focus" in content or ":focus-visible" in content
