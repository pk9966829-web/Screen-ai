import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402


def test_screen_uploads_are_not_publicly_mounted():
    assert not any(getattr(route, "path", "") == "/uploads" for route in main.app.routes)


def test_default_cors_is_not_wildcard():
    cors = next(middleware for middleware in main.app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")
    origins = cors.kwargs.get("allow_origins", [])
    assert "*" not in origins
    assert "http://localhost:1420" in origins
    assert "http://127.0.0.1:1420" in origins
