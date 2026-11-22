#!/usr/bin/env python3
"""File + HTTP assertions for the static Triage dashboard."""

from __future__ import annotations

import http.server
import socketserver
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "triage" / "web" / "static"
PANELS = ("Overview", "Systems", "Terminals", "Events", "Incidents", "Telemetry")
API_PATHS = (
    "/api/overview",
    "/api/assets",
    "/api/events",
    "/api/incidents",
    "/api/terminals",
    "/api/telemetry",
    "/api/stream",
)


def _read_all() -> str:
    chunks = []
    for path in STATIC.rglob("*"):
        if path.suffix in {".html", ".css", ".js"}:
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


class DashboardStaticTests(unittest.TestCase):
    def test_required_files_exist(self):
        for rel in (
            "index.html",
            "styles.css",
            "app.js",
            "fixtures.js",
            "js/api.js",
            "js/sse.js",
            "js/state.js",
            "js/theme.js",
            "js/views/overview.js",
            "js/views/systems.js",
            "js/views/terminals.js",
            "js/views/events.js",
            "js/views/incidents.js",
            "js/views/telemetry.js",
        ):
            self.assertTrue((STATIC / rel).is_file(), rel)

    def test_panels_and_theme_tokens(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        for name in PANELS:
            self.assertIn(name, html)
        self.assertIn("data-theme", html)
        self.assertIn("[data-theme=", css)
        self.assertIn("Triage", html)
        self.assertIn("theme-toggle", html)
        self.assertIn("prefers-color-scheme", html)
        self.assertIn("triage-theme", html)

    def test_dark_and_light_css_variables(self):
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        self.assertIn('[data-theme="light"]', css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("#12141a", css)
        self.assertIn("#f3f1ea", css)
        self.assertIn("#1a1d24", css)
        self.assertIn("#fffdf8", css)
        self.assertIn("--accent", css)
        self.assertIn("--danger", css)
        self.assertNotIn("linear-gradient", css)

    def test_api_paths_present(self):
        blob = _read_all()
        for path in API_PATHS:
            self.assertIn(path, blob)

    def test_views_do_not_fetch(self):
        for path in (STATIC / "js" / "views").glob("*.js"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("fetch(", text, path.name)
            self.assertNotIn("EventSource", text, path.name)

    def test_api_client_does_not_touch_dom(self):
        text = (STATIC / "js" / "api.js").read_text(encoding="utf-8")
        self.assertNotIn("document.", text)
        self.assertNotIn("innerHTML", text)
        self.assertNotIn("querySelector", text)

    def test_fixtures_cover_kinds_and_statuses(self):
        text = (STATIC / "fixtures.js").read_text(encoding="utf-8")
        for kind in ("process", "terminal", "server", "url", "deploy"):
            self.assertIn(f'kind: "{kind}"', text)
        for status in ("up", "down", "degraded", "unknown"):
            self.assertIn(f'status: "{status}"', text)
        self.assertIn("last_lines", text)
        self.assertIn("actions", text)
        self.assertIn("report_path", text)
        self.assertIn("escalate_reason", text)
        self.assertIn("heartbeats", text)

    def test_http_serves_index_and_modules(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(STATIC), **kwargs)

            def log_message(self, format, *args):
                return

        httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            index = (
                urllib.request.urlopen(base + "/index.html?mock=1", timeout=3)
                .read()
                .decode()
            )
            self.assertIn("Triage", index)
            for name in PANELS:
                self.assertIn(name, index)
            css = (
                urllib.request.urlopen(base + "/styles.css", timeout=3).read().decode()
            )
            self.assertIn("--bg", css)
            js = urllib.request.urlopen(base + "/app.js", timeout=3).read().decode()
            self.assertIn("renderOverview", js)
            api_js = (
                urllib.request.urlopen(base + "/js/api.js", timeout=3).read().decode()
            )
            self.assertIn("/api/overview", api_js)
            fixtures = (
                urllib.request.urlopen(base + "/fixtures.js", timeout=3).read().decode()
            )
            self.assertIn("open_incidents", fixtures)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
