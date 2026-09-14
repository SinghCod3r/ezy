"""HTTP support, built on `requests`.

TLS certificate verification is always on; there is no language-level
knob to disable it (a deliberate deviation from "curl-level capability"
in the master spec — see docs/limitations.md). Redirects are followed
using requests' defaults. Credentials passed via headers are never
logged by the interpreter.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from ..errors import EzyRuntimeError
from ..values import HttpResponse

DEFAULT_TIMEOUT = 30.0


def request(method: str, url: str, headers: Optional[Dict[str, str]] = None,
            params: Optional[Dict[str, Any]] = None, json_body: Optional[Any] = None,
            timeout: Optional[float] = None) -> HttpResponse:
    if not isinstance(url, str) or not url.strip():
        raise EzyRuntimeError("a URL must be a non-empty string", "HttpError")
    start = time.monotonic()
    try:
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=timeout or DEFAULT_TIMEOUT,
        )
        elapsed = (time.monotonic() - start) * 1000
        return HttpResponse(
            status=resp.status_code,
            text=resp.text,
            headers=dict(resp.headers),
            url=resp.url,
            ok=resp.ok,
            elapsed_ms=elapsed,
        )
    except requests.exceptions.Timeout:
        return HttpResponse(status=0, text="", headers={}, url=url, ok=False, error="request timed out")
    except requests.exceptions.SSLError as exc:
        return HttpResponse(status=0, text="", headers={}, url=url, ok=False, error=f"TLS error: {exc}")
    except requests.exceptions.ConnectionError as exc:
        return HttpResponse(status=0, text="", headers={}, url=url, ok=False, error=f"connection failed: {exc}")
    except requests.exceptions.RequestException as exc:
        return HttpResponse(status=0, text="", headers={}, url=url, ok=False, error=str(exc))


def download(url: str, destination: str, timeout: Optional[float] = None) -> HttpResponse:
    if not isinstance(url, str) or not url.strip():
        raise EzyRuntimeError("a URL must be a non-empty string", "HttpError")
    try:
        with requests.get(url, stream=True, timeout=timeout or DEFAULT_TIMEOUT) as resp:
            resp.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            return HttpResponse(
                status=resp.status_code, text="", headers=dict(resp.headers),
                url=resp.url, ok=True,
            )
    except requests.exceptions.RequestException as exc:
        return HttpResponse(status=0, text="", headers={}, url=url, ok=False, error=str(exc))
    except OSError as exc:
        raise EzyRuntimeError(f"could not save download to {destination!r}: {exc.strerror}", "FileError") from exc
