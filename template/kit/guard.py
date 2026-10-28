"""Guards: screen what comes in, what is stored, and what goes out.

Text crosses a trust boundary in four places, and each gets a check:

    prompt   the user's message, before the model sees it
    data     documents at ingestion and every tool result, before the model sees them
    egress   what an outbound tool is about to send (a post, a message, an email)
    output   the answer, before the user sees it

Rules run first and always. They are deterministic, so no prompt can argue with them:

    hidden     invisible characters are removed: Unicode tag characters (which spell
               out ASCII people cannot see), variation selectors (which can carry a
               byte each), zero-width and other format characters, bidi controls;
               in data, also HTML comments and script, style, template and noscript
               blocks, and markup styled to be invisible is flagged
    secrets    credentials are redacted, and never leave in a message
    pii        card numbers, resident registration numbers and SSNs are redacted;
               add "email" and "phone" to redact those too
    exfil      answers and outbound messages only point at https URLs on hosts you
               list, and images never carry a query string, because a URL the model
               writes is a way out of the session; with no hosts listed, nothing remote
    injection  instruction-like text in data is flagged for the trace, not removed:
               no rule can separate every instruction from ordinary text

A classifier (a guard model or a moderation API, see the adapters below) covers
what rules cannot see, such as harassment, self-harm or a custom content policy.
It is one layer on top of the rules, never the only one.

What holds even if the model is completely fooled: no hidden characters reach it,
no credential or protected number leaves through an answer or a message, and no
answer carries data out through an image or a link. What no guard can promise is
that the model ignores instructions written in plain sight; for that, tools.py
decides what any instruction can actually do (permissions, the trifecta rule,
approvals, lockdown).
"""

import json
import os
import re
import urllib.parse
from dataclasses import dataclass, field, replace
from typing import Callable

from .net import post


@dataclass(frozen=True)
class Finding:
    rule: str    # e.g. "secret.github", "pii.card", "hidden.tags", "exfil.image", "moderation.violence"
    action: str  # "strip" | "redact" | "block" | "flag"

    def __str__(self) -> str:
        return f"{self.rule}:{self.action}"


@dataclass
class Verdict:
    text: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.action == "block" for f in self.findings)

    @property
    def labels(self) -> list[str]:
        return sorted({str(f) for f in self.findings})


# ---------------------------------------------------------------- rules

# Characters people cannot see but models read, each used in a published attack: tag characters
# ("ASCII smuggling"), variation selectors ("emoji smuggling"; one U+FE0E/FE0F after a character
# is legitimate, so only repeats go), zero-width and format characters ("Sneaky Bits" encodes
# bits as U+2062/U+2064), bidi controls ("Trojan Source") and lone surrogates. Stripping U+200D
# also splits joined emoji, which is the price of a rule with no exceptions to argue about.
TAGS = re.compile("[\U000E0000-\U000E007F]+")
SELECTORS = re.compile("[\U000E0100-\U000E01EF\uFE00-\uFE0D]+|(?<=[\uFE0E\uFE0F])[\uFE0E\uFE0F]+")
INVISIBLE = re.compile("[\u00AD\u061C\u180E\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u2069\uFEFF\uD800-\uDFFF]+")
HIDDEN_HTML = re.compile(r"<!--[\s\S]*?-->|<(script|style|template|noscript)\b[\s\S]*?</\1\s*>", re.I)
HIDDEN_STYLE = re.compile(r"<[a-z][^>]*(?:\shidden\b|aria-hidden\s*=\s*[\"']?true|display\s*:\s*none"
                          r"|visibility\s*:\s*hidden|opacity\s*:\s*0(?:\.0+)?(?![.\d])|font-size\s*:\s*0(?![.\d]))", re.I)


def reveal(text: str) -> str:
    """What a hidden tag-character payload says (models read it; people cannot)."""
    return "".join(chr(ord(c) - 0xE0000) for c in text if 0xE0020 <= ord(c) <= 0xE007E)


# Credential formats, after the default rules in gitleaks' config/gitleaks.toml (2025-11-20), widened
# where a vendor issues more than one format. A redaction rule should over-match, not under-match.
SECRETS = {
    "slack_webhook": r"(?:https?://)?hooks\.slack\.com/(?:services|workflows|triggers)/[A-Za-z0-9+/]{43,56}",
    "aws": r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16}\b",
    "github": r"\b(?:gh[pousr]_[0-9a-zA-Z]{36}|github_pat_\w{82})\b",
    "openai": r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}T3BlbkFJ[A-Za-z0-9_-]{20,}",
    "anthropic": r"\bsk-ant-(?:api|admin)\d\d-[\w-]{80,}",
    "slack": r"\bxox[abposr]-[0-9A-Za-z-]{10,}",
    "google": r"\bAIza[\w-]{35}\b",
    "stripe": r"\b(?:sk|rk)_(?:test|live|prod)_[0-9a-zA-Z]{10,99}\b",
    "private_key": r"-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----[\s\S]*?-----END[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----",
    "jwt": r"\bey[a-zA-Z0-9]{17,}\.ey[a-zA-Z0-9/\\_-]{17,}\.[a-zA-Z0-9/\\_-]{10,}={0,2}",
}
# ASCII mode: \b must treat Hangul and other scripts as boundaries, so "키는ghp_…입니다" still matches.
SECRETS = {name: re.compile(p, re.ASCII) for name, p in SECRETS.items()}


def luhn(number: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", number)][::-1]
    return sum(d if i % 2 == 0 else (d * 2 - 9 if d > 4 else d * 2) for i, d in enumerate(digits)) % 10 == 0


PII = {
    "card": (r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", luhn),
    # 주민등록번호 and 외국인등록번호 (7th digit 5-8). No checksum: numbers issued since October 2020
    # end in random digits, so a failed check digit must never clear a match.
    "rrn": (r"(?<!\d)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])-?[1-8]\d{6}(?!\d)", None),
    "ssn": (r"(?<!\d)(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?!\d)", None),
    "email": (r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", None),
    "phone": (r"(?<![\d-])(?:\+\d{1,3}[ -]?)?\(?\d{2,4}\)?[ -]?\d{3,4}[ -]\d{4}(?![\d-])", None),
}
PII = {name: (re.compile(p, re.ASCII), check) for name, (p, check) in PII.items()}

IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]*)>?[^)]*\)")
HTML_IMAGE = re.compile(r"<img\b[^>]*>", re.I)
LINK = re.compile(r"(?<!!)\[([^\]]+)\]\(\s*<?([^)\s>]+)>?[^)]*\)")
URL = re.compile(r"\b(?:https?|ftp)://[^\s<>\]\)\"']+", re.I)

INSTRUCTIONS = re.compile(
    r"(?im)^\W*(?:system|assistant|developer)\s*:"
    r"|\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|your\s+|the\s+)*(?:previous|prior|above|earlier)\s+(?:instructions|rules|prompts?)"
    r"|\byou\s+are\s+now\b|\bnew\s+instructions?\s*:")


# ---------------------------------------------------------------- the guard

class Guard:
    refusal = "I can't help with that request."
    withheld = "I can't share that answer."

    def __init__(self, pii: tuple = ("card", "rrn", "ssn"), hosts: tuple = (),
                 classify: Callable[[str, str], list[Finding]] | None = None, classify_data: bool = False):
        self.pii = {name: PII[name] for name in pii}
        self.hosts = tuple(h.lower() for h in hosts)
        self.classify, self.classify_data = classify, classify_data

    @property
    def settings(self) -> dict:
        """Part of the release: changing what the guard screens changes behaviour."""
        classifier = self.classify and f"{type(self.classify).__name__}:{getattr(self.classify, 'model', '')}"
        return {"pii": sorted(self.pii), "hosts": list(self.hosts), "classifier": classifier,
                "classify_data": self.classify_data}

    def prompt(self, text: str) -> Verdict:
        return self._screen(text, "prompt")

    def data(self, text: str) -> Verdict:
        return self._screen(text, "data")

    def egress(self, text: str) -> Verdict:
        return self._screen(text, "egress")

    def output(self, text: str) -> Verdict:
        return self._screen(text, "output")

    def documents(self, docs: list) -> list:
        """Clean documents once, at ingestion, so the index never holds what the model must not see."""
        return [replace(d, text=self.data(d.text).text) for d in docs]

    def _screen(self, text: str, stage: str) -> Verdict:
        found: list[Finding] = []
        # Egress refuses instead of editing: a person approved this message, not a redacted one.
        edit = "block" if stage == "egress" else None

        def sub(pattern, rule, action, repl, check=None):
            nonlocal text

            def one(m):
                if check and not check(m.group(0)):
                    return m.group(0)
                found.append(Finding(rule, edit or action))
                return repl(m) if callable(repl) else repl
            text = pattern.sub(one, text)

        sub(TAGS, "hidden.tags", "strip", "")
        sub(SELECTORS, "hidden.selectors", "strip", "")
        sub(INVISIBLE, "hidden.invisible", "strip", "")
        if stage == "data":
            sub(HIDDEN_HTML, "hidden.html", "strip", "")
            if HIDDEN_STYLE.search(text):  # no regex can find where such an element ends, so flag it
                found.append(Finding("hidden.styled", "flag"))
        for name, pattern in SECRETS.items():
            sub(pattern, f"secret.{name}", "redact", f"[REDACTED:{name}]")
        for name, (pattern, check) in self.pii.items():
            sub(pattern, f"pii.{name}", "redact", f"[REDACTED:{name}]", check)
        if stage in ("output", "egress"):
            sub(IMAGE, "exfil.image", "strip", "[image removed]",
                lambda s: not self._safe(IMAGE.match(s).group(2), image=True))
            sub(HTML_IMAGE, "exfil.image", "strip", "[image removed]", lambda s: not self._safe_html(s))
            sub(LINK, "exfil.link", "strip", lambda m: f"{m.group(1)} [link removed]",
                lambda s: not self._safe(LINK.match(s).group(2)))
            sub(URL, "exfil.link", "strip", "[link removed]", lambda s: not self._safe(s))
        if stage == "data" and INSTRUCTIONS.search(text):
            found.append(Finding("injection.suspected", "flag"))
        if self.classify and (stage in ("prompt", "output") or (stage == "data" and self.classify_data)):
            found += self.classify(text, stage)
        return Verdict(text, found)

    def _safe(self, url: str, image: bool = False) -> bool:
        """Relative links stay. Absolute ones need https and a listed host (or a subdomain of one);
        images also need no query string, since that is where exfiltrated data rides."""
        if not re.match(r"(?i)^(?:[a-z][a-z0-9+.-]*:|//)", url):
            return True
        parts = urllib.parse.urlsplit("https:" + url if url.startswith("//") else url)
        if parts.scheme.lower() != "https" or (image and parts.query):
            return False
        host = (parts.hostname or "").rstrip(".").lower()
        return any(host == h or host.endswith("." + h) for h in self.hosts)

    def _safe_html(self, tag: str) -> bool:
        src = re.search(r"""src\s*=\s*["']?([^"'\s>]+)""", tag, re.I)
        return not src or self._safe(src.group(1), image=True)


# ---------------------------------------------------------------- classifiers
# A classifier is classify(text, stage) -> list[Finding]; stage is "prompt", "data" or "output".
# Model names are configuration; check the current ones before relying on any default here.

class OpenAIModeration:
    """OpenAI moderation endpoint: text (and image) categories, flagged per category."""

    def __init__(self, model: str = "omni-moderation-latest", api_key: str | None = None,
                 url: str = "https://api.openai.com/v1/moderations"):
        self.model, self.url = model, url
        self.api_key = api_key or os.environ["OPENAI_API_KEY"]

    def __call__(self, text: str, stage: str) -> list[Finding]:
        out = post(self.url, {"authorization": f"Bearer {self.api_key}"}, {"model": self.model, "input": text})
        result = out["results"][0]
        return [Finding(f"moderation.{name}", "block") for name, hit in result["categories"].items() if hit]


class GuardModel:
    """An open guard model behind any OpenAI-compatible chat endpoint (vLLM, SGLang, Ollama).

    format="llama-guard"  Llama Guard 3/4: replies "safe", or "unsafe" and a line of codes like "S1,S10".
                          English and seven other languages; not Korean.
    format="qwen3guard"   Qwen3Guard-Gen: replies "Safety: Safe|Unsafe|Controversial" and "Categories: ...".
                          119 languages, Korean included. Controversial passes unless block_controversial.
    format="policy"       a policy-following guard such as gpt-oss-safeguard: your policy (400-600 tokens
                          works best) is the system prompt, and it answers with the label your policy
                          asks for: `unsafe` on the last line, or JSON with a truthy "violation"

    Other guards (Kanana Safeguard, Granite Guardian, Shieldstral, WildGuard) need their own prompt
    format; see sota/ladders.md and add a format here when you adopt one.
    """

    def __init__(self, model: str, base_url: str, format: str = "llama-guard", policy: str = "",
                 unsafe: str = "1", block_controversial: bool = False, api_key: str | None = None):
        assert format in ("llama-guard", "qwen3guard", "policy")
        self.model, self.base_url, self.format = model, base_url.rstrip("/"), format
        self.policy, self.unsafe, self.block_controversial = policy, unsafe, block_controversial
        self.api_key = api_key or os.environ.get("GUARD_API_KEY", "none")

    def __call__(self, text: str, stage: str) -> list[Finding]:
        if self.format == "policy":
            messages = [{"role": "system", "content": self.policy}, {"role": "user", "content": text}]
        elif stage == "output":  # judge the answer as an assistant turn
            messages = [{"role": "user", "content": "(not shown)"}, {"role": "assistant", "content": text}]
        else:
            messages = [{"role": "user", "content": text}]
        out = post(f"{self.base_url}/chat/completions", {"authorization": f"Bearer {self.api_key}"},
                   {"model": self.model, "messages": messages, "temperature": 0})
        return self.parse(out["choices"][0]["message"]["content"] or "")

    def parse(self, reply: str) -> list[Finding]:
        reply = reply.strip()
        if self.format == "llama-guard":
            lines = reply.splitlines()
            if not lines or lines[0].strip().lower() != "unsafe":
                return []
            codes = lines[1].split(",") if len(lines) > 1 else ["unsafe"]
            return [Finding(f"moderation.{c.strip()}", "block") for c in codes if c.strip()]
        if self.format == "qwen3guard":
            safety = re.search(r"Safety:\s*(\w+)", reply)
            label = safety.group(1).lower() if safety else "safe"
            if label == "safe" or (label == "controversial" and not self.block_controversial):
                return []
            cats = re.search(r"Categories:\s*(.+)", reply)
            names = [c.strip() for c in cats.group(1).split(",")] if cats else [label]
            return [Finding(f"moderation.{n.lower().replace(' ', '_')}", "block") for n in names if n and n != "None"]
        try:
            verdict = json.loads(reply[reply.index("{"): reply.rindex("}") + 1])
            violated = bool(verdict.get("violation"))
            rule = verdict.get("policy_category") or "policy"
        except ValueError:
            violated, rule = (reply.splitlines()[-1].strip() if reply else "") == self.unsafe, "policy"
        return [Finding(f"moderation.{rule}", "block")] if violated else []
