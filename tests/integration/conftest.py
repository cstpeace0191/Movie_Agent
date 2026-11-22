"""Browser test base (feature 002, T088).

Fixtures here are opt-in: only tests marked ``@pytest.mark.browser`` that request them start a
server or a browser. The server runs as a subprocess against a temporary SQLite database and
storage folder, so browser tests never touch the developer database.

Set ``MOVIE_SKIP_CLIENT_BUILD=1`` to reuse an existing client build.
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AXE_PATH = REPO_ROOT / "client" / "node_modules" / "axe-core" / "axe.min.js"


@dataclass(frozen=True)
class LiveServer:
    base_url: str
    database_url: str


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def client_build() -> None:
    """Build the React client once per session (copied into server/app/static by the build)."""
    if os.getenv("MOVIE_SKIP_CLIENT_BUILD") == "1":
        return
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    subprocess.run(
        [npm, "--prefix", str(REPO_ROOT / "client"), "run", "build"],
        check=True,
        capture_output=True,
        timeout=600,
    )


@pytest.fixture(scope="session")
def live_server(client_build, tmp_path_factory) -> Iterator[LiveServer]:
    """Start the API (serving the built client) on a free port with ENV=test and the mock engine."""
    work = tmp_path_factory.mktemp("browser_server")
    database_url = f"sqlite:///{(work / 'browser.db').as_posix()}"
    port = _free_port()
    env = {
        **os.environ,
        "ENV": "test",  # job submission does not dispatch Celery tasks in test mode
        "VIDEO_PROVIDER": "mock",
        "DATABASE_URL": database_url,
        "STORAGE_DIR": str(work / "storage"),
        "MAIL_SERVER_ENABLED": "false",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
            raise RuntimeError(f"Test server exited early:\n{err[-2000:]}")
        try:
            if httpx.get(f"{base_url}/api/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.3)
    else:
        proc.terminate()
        raise RuntimeError("Test server did not become healthy within 60 s")

    yield LiveServer(base_url=base_url, database_url=database_url)

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def _session_cookie(server: LiveServer, username: str) -> str:
    """Create (or reuse) a verified user in the live server's database and return a session token."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from server.app.auth import create_session, hash_password
    from server.app.models import User

    engine = create_engine(server.database_url, connect_args={"check_same_thread": False})
    db = sessionmaker(bind=engine)()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                username_lower=username.lower(),
                password_hash=hash_password("browser-password-123"),
                email=f"{username}@example.test",
                email_verified=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        raw_token, _, _ = create_session(db, user)
        return raw_token
    finally:
        db.close()
        engine.dispose()


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    """Chromium for one test module.

    Module scope on purpose: sync Playwright runs an event loop in this thread, and keeping it
    open past the module breaks every later ``pytest.mark.asyncio`` test in the same run.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        instance = pw.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def logged_in_page(live_server: LiveServer, browser) -> Iterator[object]:
    """A Playwright page with a signed-in session, opened at the app's home page."""
    context = browser.new_context(locale="en-US")
    context.add_cookies(
        [
            {
                "name": "movie_session",
                "value": _session_cookie(live_server, "browser_tester"),
                "url": live_server.base_url,
            }
        ]
    )
    # Show the English UI so tests can match visible text.
    context.add_init_script("window.localStorage.setItem('movie_lang', 'en');")
    page = context.new_page()
    console: list[str] = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
    page.on(
        "response",
        lambda r: console.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )
    page.goto(live_server.base_url + "/")
    try:
        page.wait_for_selector("#job-form", timeout=20000)
    except Exception as exc:
        body = page.inner_text("body")[:800]
        raise RuntimeError(
            "Job form did not appear. Page shows:\n" + body + "\nConsole:\n" + "\n".join(console)
        ) from exc
    yield page
    context.close()


def axe_scan(page) -> list[dict]:
    """Run axe-core on the current page and return serious or critical violations."""
    if not AXE_PATH.exists():
        raise RuntimeError("axe-core is missing; run `npm ci --prefix client`")
    page.add_script_tag(path=str(AXE_PATH))
    violations = page.evaluate("async () => (await axe.run(document)).violations")
    return [v for v in violations if v.get("impact") in ("serious", "critical")]
