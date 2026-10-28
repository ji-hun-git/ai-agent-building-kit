"""One JSON POST helper, shared by every adapter (models, embeddings, rerankers, guards).

Failures come back as APIError with the provider's own message, so "400: model not
found" reads as that, not as a bare HTTP traceback. Rate limits and overload are retried a few
times first, waiting as long as the server's Retry-After asks.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


class APIError(RuntimeError):
    """A call to a model or service failed; the message says why, in the provider's words."""


def key(name: str, given: str | None = None) -> str:
    """An API key passed in, or from the environment, or a clear error saying which to set."""
    value = given or os.environ.get(name)
    if not value:
        raise APIError(f"no API key: set {name} or pass api_key=")
    return value


def key_for(url: str, vendor_host: str, name: str, given: str | None = None) -> str:
    """The vendor's key only for the vendor's own host; any other server gets LLM_API_KEY (or
    "none"), so a vendor key is never sent to a server that is not the vendor."""
    if given:
        return given
    if urllib.parse.urlsplit(url).hostname == vendor_host:
        return key(name)
    return os.environ.get("LLM_API_KEY", "none")


# Seconds to wait for one answer. A long reasoning answer can take minutes, so this matches the
# vendor SDKs' ten-minute default; set kit.net.TIMEOUT to change it for every adapter.
TIMEOUT = 600
# Answers worth asking again for: rate limits, overload (529 is Anthropic's), and a gateway that
# dropped the call. RETRIES more attempts after the first; set kit.net.RETRIES = 0 to fail fast.
RETRY_ON = {429, 500, 502, 503, 504, 529}
RETRIES = 3


def wait(retry_after, attempt: int) -> float:
    """The server's Retry-After in seconds, capped at a minute; without one, 1, 2, then 4 seconds."""
    try:
        return max(0.0, min(float(retry_after), 60.0))
    except (TypeError, ValueError):
        return float(2 ** attempt)


def post(url: str, headers: dict, body: dict, timeout: float | None = None) -> dict:
    for attempt in range(RETRIES + 1):
        try:
            return _post(url, headers, body, timeout)
        except urllib.error.HTTPError as e:
            if e.code in RETRY_ON and attempt < RETRIES:
                time.sleep(wait((e.headers or {}).get("retry-after"), attempt))
                continue
            detail = e.read().decode("utf-8", "replace").strip()[:500]
            raise APIError(f"{e.code} from {url}: {detail or e.reason}") from None
    raise AssertionError("unreachable")


def _post(url: str, headers: dict, body: dict, timeout: float | None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as resp:
            return json.load(resp)
    except urllib.error.HTTPError:  # post() decides: retry, or report in the provider's words
        raise
    except urllib.error.URLError as e:
        raise APIError(f"cannot reach {url}: {e.reason}") from None
    except OSError as e:  # a timeout or a dropped connection, part-way through the answer
        raise APIError(f"no complete answer from {url}: {e or type(e).__name__}") from None
    except ValueError:  # a proxy's error page, or anything else that is not JSON
        raise APIError(f"the answer from {url} was not JSON") from None
