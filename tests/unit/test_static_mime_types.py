import mimetypes

import server.app.main  # noqa: F401  (importing registers the static MIME types)


def test_static_assets_have_browser_mime_types():
    """Windows can map .js to text/plain from the registry; browsers then refuse module scripts."""
    assert mimetypes.guess_type("index-abc.js")[0] == "text/javascript"
    assert mimetypes.guess_type("index-abc.css")[0] == "text/css"
