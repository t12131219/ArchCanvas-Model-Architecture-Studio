"""Explicit loopback session client. Never imports or executes user models."""
import json
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from urllib.error import HTTPError, URLError


def request(server: str, path: str, payload: dict | None = None, method="POST") -> dict:
    parsed = urlsplit(server)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("The canvas client requires an explicit loopback HTTP service URL.")
    base = server.rstrip("/")
    opener = build_opener(ProxyHandler({}))
    try:
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            with opener.open(base + "/api/session", timeout=10) as response:
                headers["X-ArchCanvas-Session"] = json.load(response)["token"]
        req = Request(base + path, data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode() if payload is not None else None,
                      method=method if payload is not None else "GET", headers=headers)
        with opener.open(req, timeout=60) as response:
            return json.load(response)
    except HTTPError as exc:
        try: error = json.loads(exc.read()).get("error", str(exc))
        except ValueError: error = str(exc)
        raise ValueError(error) from exc
    except URLError as exc:
        raise ValueError(f"Studio service is unavailable at {base}; start serve with an independent --data-dir.") from exc
