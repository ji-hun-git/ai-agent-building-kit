"""Traces: one JSON line per step, named after the OpenTelemetry GenAI conventions.

Span names follow `gen_ai.operation.name` (invoke_agent, chat, execute_tool), so
the lines map one-to-one onto OTel spans if you later export them. Every span
carries the release version, so a regression points at the change that caused it.

Prompt text, tool arguments and outputs are content. Content is dropped unless
capture=True, because traces are kept longer and read more widely than the data
they describe.
"""

import json
import time
from contextlib import contextmanager


class Tracer:
    def __init__(self, path: str | None = None, release: str = "dev", capture: bool = False):
        self.path, self.release, self.capture = path, release, capture
        self.spans: list[dict] = []

    @contextmanager
    def span(self, operation: str, **attrs):
        record = {"gen_ai.operation.name": operation, "release.version": self.release}
        record.update({k: v for k, v in attrs.items() if self.capture or not k.startswith("content.")})
        start = time.perf_counter()
        try:
            yield record
        except Exception as e:
            record["error.type"] = type(e).__name__
            raise
        finally:
            record["duration_ms"] = round((time.perf_counter() - start) * 1000, 2)
            if not self.capture:
                record = {k: v for k, v in record.items() if not k.startswith("content.")}
            self.spans.append(record)
            if self.path:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
