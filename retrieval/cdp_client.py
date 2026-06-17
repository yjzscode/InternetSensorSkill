#!/usr/bin/env python3
"""Python bridge to the web-access CDP proxy.

The web-access skill (https://github.com/eze-is/web-access) is agent-driven: an
LLM navigates a real browser step by step via a CDP proxy on localhost:3456. Our
retrieval layer is the opposite — deterministic Python CLIs. This module bridges
the two: it speaks the proxy's HTTP API (/new, /navigate, /eval, /close) so our
per-platform extractors can drive the user's *real, logged-in* browser and reach
content that static HTTP can't (小红书 / 知乎 / 微信公众号 / 豆瓣 / 虎扑 are JS-rendered,
login-gated, or selector-sensitive enough to benefit from a real browser).

Why the real browser: those platforms block server-side scraping. The proxy
attaches to the user's daily Chrome/Edge over Chrome DevTools Protocol, so every
request carries their login/session — the same reason web-access exists.

桥接 web-access 的 CDP Proxy：用 Python 调它的 HTTP API，驱动用户**真实已登录**的浏览器，
拿到小红书/知乎/微信公众号这类纯静态抓不到的内容。

Proxy lifecycle is owned by the skill's own `check-deps.mjs` (it boots the proxy
and connects the browser). We only call the HTTP API and, if the proxy isn't up,
shell out to check-deps once to start it.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import requests


PROXY_HOST = os.environ.get("CDP_PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.environ.get("CDP_PROXY_PORT", "3456"))
BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}"

# Where the web-access skill lives. Overridable; defaults to skills/web-access
# under the project root (two levels up from this file: retrieval/ -> project).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = Path(os.environ.get(
    "WEB_ACCESS_SKILL_DIR", str(_PROJECT_ROOT / "skills" / "web-access")
))


class CDPError(RuntimeError):
    """Raised when the CDP proxy is unavailable or a browser op fails."""


class ConsentRequired(RuntimeError):
    """Raised when CDP retrieval is attempted without the user's explicit consent.

    Driving the user's real, logged-in browser carries account risk (automation
    detection, session use), so it must never happen silently. The dispatcher
    catches this and asks the user before any browser is touched.
    """


class CDPClient:
    """Thin client over the web-access CDP proxy HTTP API.

    Typical use:
        with CDPClient() as cdp:
            cdp.ensure_proxy()                  # boot proxy + browser if needed
            tid = cdp.new_tab("https://...")
            data = cdp.eval(tid, "(() => {...})()")
    Tabs created via `new_tab` are tracked and closed on context exit, matching
    web-access's "minimal footprint: clean up your own tabs" philosophy.
    """

    def __init__(self, timeout: int = 30, skill_dir: Path = SKILL_DIR):
        self.timeout = timeout
        self.skill_dir = Path(skill_dir)
        self._own_tabs = []

    # -- lifecycle -----------------------------------------------------------

    def health(self) -> dict:
        """Return the proxy /health dict, or {} if the proxy isn't reachable."""
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=3)
            return r.json()
        except (requests.RequestException, ValueError):
            return {}

    def is_ready(self) -> bool:
        """True if the proxy is up AND connected to a browser."""
        h = self.health()
        return bool(h.get("status") == "ok" and h.get("connected"))

    def ensure_proxy(self, browser: str = "") -> None:
        """Make sure the proxy is up and a browser is attached.

        If not ready, run the skill's check-deps.mjs once (it boots the proxy and
        connects the browser). Raises CDPError with the actionable browser-enable
        instruction when the browser hasn't opted into remote debugging — that
        toggle is a manual user step the skill can't do for them.
        """
        if self.is_ready():
            return

        check = self.skill_dir / "scripts" / "check-deps.mjs"
        if not check.exists():
            raise CDPError(
                f"web-access skill not found at {self.skill_dir}. "
                f"Clone it there or set WEB_ACCESS_SKILL_DIR."
            )

        cmd = ["node", str(check)]
        if browser:
            cmd += ["--browser", browser]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            raise CDPError(f"failed to run check-deps.mjs: {exc}") from exc

        if not self.is_ready():
            # Surface check-deps' own guidance — it explains the remote-debugging toggle.
            hint = (proc.stdout or "").strip() or (proc.stderr or "").strip()
            raise CDPError(
                "CDP proxy is not connected to a browser. The browser must opt into "
                "remote debugging (a one-time manual step):\n"
                "  In Chrome/Edge, open chrome://inspect/#remote-debugging (or "
                "edge://inspect/#remote-debugging) and tick "
                '"Allow remote debugging for this browser instance".\n'
                f"--- check-deps output ---\n{hint}"
            )

    # -- tabs ----------------------------------------------------------------

    def new_tab(self, url: str = "about:blank") -> str:
        """Create a background tab (POST /new, body=URL). Returns its targetId."""
        r = requests.post(f"{BASE_URL}/new", data=url.encode("utf-8"), timeout=self.timeout)
        r.raise_for_status()
        target_id = r.json().get("targetId")
        if not target_id:
            raise CDPError(f"/new returned no targetId: {r.text[:200]}")
        self._own_tabs.append(target_id)
        return target_id

    def navigate(self, target_id: str, url: str) -> None:
        """Navigate a tab and wait for load (POST /navigate?target=ID, body=URL)."""
        r = requests.post(f"{BASE_URL}/navigate", params={"target": target_id},
                          data=url.encode("utf-8"), timeout=self.timeout)
        r.raise_for_status()

    def eval(self, target_id: str, expression: str):
        """Run JS in a tab (POST /eval?target=ID, body=JS). Returns the value.

        The proxy uses returnByValue + awaitPromise, so an expression that returns
        a JSON-serializable value (or a Promise of one) comes back as Python data.
        """
        r = requests.post(f"{BASE_URL}/eval", params={"target": target_id},
                          data=expression.encode("utf-8"), timeout=self.timeout)
        if r.status_code >= 400:
            try:
                err = r.json().get("error", r.text)
            except ValueError:
                err = r.text
            raise CDPError(f"/eval failed: {err}")
        return r.json().get("value")

    def scroll(self, target_id: str, times: int = 1) -> None:
        """Scroll to trigger lazy-loading (GET /scroll?target=ID)."""
        for _ in range(max(times, 0)):
            try:
                requests.get(f"{BASE_URL}/scroll", params={"target": target_id},
                            timeout=self.timeout)
            except requests.RequestException:
                break
            time.sleep(0.6)

    def close_tab(self, target_id: str) -> None:
        """Close a tab (GET /close?target=ID). Best-effort."""
        try:
            requests.get(f"{BASE_URL}/close", params={"target": target_id}, timeout=10)
        except requests.RequestException:
            pass
        if target_id in self._own_tabs:
            self._own_tabs.remove(target_id)

    # -- context management --------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        for tid in list(self._own_tabs):
            self.close_tab(tid)
        return False
