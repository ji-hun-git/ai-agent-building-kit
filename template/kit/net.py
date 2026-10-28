"""One JSON POST helper, shared by every adapter (models, embeddings, rerankers, guards).

Failures come back as APIError with the provider's own message, so "400: model not
found" reads as that, not as a bare HTTP traceback.
"""

import json
import os
import urllib.error
import urllib.request


class APIError(RuntimeError):
    """A call to a model or service failed; the message says why, in the provider's words."""


def key(name: str, given: str | None = None) -> str:
    """An API key passed in, or from the environment, or a clear error saying which to set."""
    value = given or os.environ.get(name)
    if not value:
        raise APIError(f"no API key: set {name} or pass api_key=")
    return value


def post(url: str, headers: dict, body: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace").strip()[:500]
        raise APIError(f"{e.code} from {url}: {detail or e.reason}") from None
    except urllib.error.URLError as e:
        raise APIError(f"cannot reach {url}: {e.reason}") from None
