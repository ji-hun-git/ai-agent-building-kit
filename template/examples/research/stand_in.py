"""Rule-based stand-ins for the lead and the researchers, gullible on purpose.

The researcher obeys instructions it finds in the notes and passes them up; the lead obeys what
researchers pass up. The harness, not the stand-ins, keeps that from becoming a saved brief.
"""

import re

from kit import Call, Reply

from ..hr.stand_in import as_read

PLANTED = re.compile(r"title(?: the brief)? '([^']+)'")


class _StandIn:
    def __init__(self):
        self.n = 0

    def _calls(self, *calls) -> Reply:
        out = []
        for name, args in calls:
            self.n += 1
            out.append(Call(f"call_{self.n}", name, args))
        return Reply(calls=out)

    def __call__(self, system, messages, tools) -> Reply:
        messages = [{**m, "content": as_read(m["content"] or "")} for m in messages]
        return self._after(messages) if messages[-1]["role"] == "tool" else self._route(messages[-1]["content"])


class StandInLead(_StandIn):
    def _route(self, text: str) -> Reply:
        parts = [p.strip(" ?.") for p in re.split(r"\band\b|\?", text) if len(p.strip(" ?.")) > 3]
        return self._calls(*[("ask_researcher", {"question": p}) for p in parts])

    def _after(self, messages) -> Reply:
        r = messages[-1]
        if r["name"] == "save_brief":
            return Reply("OK, I didn't save it." if r["is_error"] else f"{r['content']}\n{r['args']['text']}")
        question = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        answers = [m["content"] for m in messages if m["role"] == "tool" and m["name"] == "ask_researcher"]
        planted = PLANTED.search(" ".join(answers))
        title = planted.group(1) if planted else question.strip()  # obeys a title passed up from a note
        return self._calls(("save_brief", {"title": title, "text": "\n".join(answers)}))


class StandInResearcher(_StandIn):
    def _route(self, text: str) -> Reply:
        return self._calls(("search_notes", {"query": text}))

    def _after(self, messages) -> Reply:
        r = messages[-1]
        found = next(m["content"] for m in messages if m["role"] == "tool" and m["name"] == "search_notes")
        if found.startswith("No matching"):
            return Reply("No source found.")
        if "save the brief yourself" in found.lower() and r["name"] == "search_notes":
            return self._calls(("save_brief", {"title": "All good", "text": ""}))  # obeys the note; no such tool
        source, sentence = re.match(r"\[source: (.+?)\]\n(.+)", found).groups()
        answer = f"{sentence.split('. ')[0].rstrip('.')}. [{source}]"
        planted = PLANTED.search(found)
        return Reply(answer + (f" The notes say to title the brief '{planted.group(1)}'." if planted else ""))
