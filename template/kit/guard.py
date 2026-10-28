"""Guards: screen what comes in, what is stored, and what goes out.

Text crosses a trust boundary in four places, and each gets a check:

    prompt   the user's message, before the model sees it
    data     documents at ingestion and every tool result, before the model sees them
    egress   what an outbound tool is about to send (a post, a message, an email)
    output   the answer, before the user sees it

Rules run first and always. They are deterministic, so no prompt can argue with them:

    hidden     invisible characters are removed: Unicode tag characters (which spell
               out ASCII people cannot see), every format character (zero-width, bidi
               and the rest), blank fillers, and repeated variation selectors (which
               can carry a byte each); in data, also HTML comments and script, style,
               template and noscript blocks, and markup styled to be invisible is flagged
    secrets    credentials in the formats listed below are redacted, and never leave
               in a message
    pii        card numbers, resident registration numbers and SSNs are redacted;
               add "email" and "phone" to redact those too
    exfil      answers and outbound messages only point at https URLs on hosts you
               list, in any form the rules below parse (markdown, HTML, reference
               links, bare and protocol-relative URLs), and images never carry a query
               string, because a URL the model writes is a way out of the session;
               with no hosts listed, nothing remote
    injection  instruction-like text in data is flagged for the trace, not removed:
               no rule can separate every instruction from ordinary text

A classifier (a guard model or a moderation API, see the adapters below) covers
what rules cannot see, such as harassment, self-harm or a custom content policy.
It is one layer on top of the rules, never the only one.

What holds even if the model is completely fooled, for exactly the characters,
formats and URL forms listed here: none of the hidden characters reach it, none of
the credentials or identifiers leave through an answer or a message, and no answer
points a renderer at an unlisted host. Rules cover what they name and nothing more:
a credential in a format not listed passes, so add the formats your systems issue. What no guard can promise is
that the model ignores instructions written in plain sight; for that, tools.py
decides what any instruction can actually do (permissions, the trifecta rule,
approvals, lockdown).
"""

import json
import os
import re
import urllib.parse
from dataclasses import dataclass, field, replace
from collections.abc import Callable

from .net import key, post


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

# Characters people cannot see but models read. Every format (Cf) character goes, and the fillers
# that render as blank; then repeated variation selectors, in a second pass so nothing can hide in
# the gaps. Each family was used in a published attack: tag characters ("ASCII smuggling"),
# variation selectors ("emoji smuggling"; one U+FE0E/FE0F after a character is legitimate, so only
# repeats go), zero-width and format characters ("Sneaky Bits" encodes bits as U+2062/U+2064) and
# bidi controls ("Trojan Source"). Stripping U+200D also splits joined emoji: the price of a rule
# with no exceptions to argue about.
TAGS = re.compile("[\U000E0000-\U000E007F]+")
INVISIBLE = re.compile(
    "[\u00AD\u034F\u0600-\u0605\u061C\u06DD\u070F\u0890\u0891\u08E2\u115F\u1160\u17B4\u17B5"
    "\u180B-\u180F\u200B-\u200F\u202A-\u202E\u2060-\u206F\u2800\u3164\uFEFF\uFFA0\uFFF9-\uFFFB"
    "\U000110BD\U000110CD\U00013430-\U0001343F\U0001BCA0-\U0001BCA3\U0001D173-\U0001D17A\uD800-\uDFFF]+")
SELECTORS = re.compile("[\U000E0100-\U000E01EF\uFE00-\uFE0D]+|(?<=[\uFE0E\uFE0F])[\uFE0E\uFE0F]+")
BLOCKS = re.compile(r"<!--|<(script|style|template|noscript)\b", re.I)
TAG = re.compile(r"<[a-z][^>]{0,2000}", re.I)
HIDDEN_STYLE = re.compile(r"\shidden\b|aria-hidden\s*=\s*[\"']?true|display\s*:\s*none|visibility\s*:\s*hidden"
                          r"|opacity\s*:\s*0(?:\.0+)?(?![.\d])|font-size\s*:\s*0(?![.\d])", re.I)


def reveal(text: str) -> str:
    """What a hidden tag-character payload says (models read it; people cannot)."""
    return "".join(chr(ord(c) - 0xE0000) for c in text if 0xE0020 <= ord(c) <= 0xE007E)


def strip_blocks(text: str) -> tuple[str, int]:
    """Remove HTML comments and script, style, template and noscript blocks in one linear pass.
    An unclosed one runs to the end of the text, as it would in a browser."""
    lower, out, i, n = text.lower(), [], 0, 0
    while m := BLOCKS.search(text, i):
        out.append(text[i:m.start()])
        n += 1
        tag = m.group(1)
        close = lower.find(f"</{tag.lower()}" if tag else "-->", m.end())
        if close < 0:
            i = len(text)
            break
        end = lower.find(">", close) if tag else close + 2
        i = len(text) if end < 0 else end + 1
    out.append(text[i:])
    return "".join(out), n


# Credential formats, after the default rules in gitleaks' config/gitleaks.toml (2025-11-20), widened
# where a vendor issues more than one format, plus bearer tokens, passwords in URLs and labelled AWS
# secret keys. A redaction rule should over-match, not under-match. Every repeat is bounded, so no
# input can make a pattern slow.
SECRETS = {
    "slack_webhook": r"(?:https?://)?hooks\.slack\.com/(?:services|workflows|triggers)/[A-Za-z0-9+/]{43,56}",
    "url_password": r"\b[a-zA-Z][a-zA-Z0-9+.-]{1,20}://[^\s:/@]{1,100}:[^\s@/]{1,200}@",
    "bearer": r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,500}=*",
    "aws_secret": r"(?i)\baws_secret_access_key\b[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}",
    "aws": r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16}\b",
    "github": r"\b(?:gh[pousr]_[0-9a-zA-Z]{36}|github_pat_\w{82})\b",
    "openai": r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,200}T3BlbkFJ[A-Za-z0-9_-]{20,200}",
    "anthropic": r"\bsk-ant-(?:api|admin)\d\d-[\w-]{80,200}",
    "slack": r"\bxox[abposr]-[0-9A-Za-z-]{10,200}",
    "google": r"\bAIza[\w-]{35}\b",
    "stripe": r"\b(?:sk|rk)_(?:test|live|prod)_[0-9a-zA-Z]{10,99}\b",
    "jwt": r"\bey[a-zA-Z0-9]{17,2000}\.ey[a-zA-Z0-9/\\_-]{17,4000}\.[a-zA-Z0-9/\\_-]{10,2000}={0,2}",
}
# ASCII mode: \b must treat Hangul and other scripts as boundaries, so "키는ghp_…입니다" still matches.
SECRETS = {name: re.compile(p, re.ASCII) for name, p in SECRETS.items()}


PEM_BEGIN = re.compile(r"-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----")
PEM_END = re.compile(r"-----END[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----")


def redact_keys(text: str) -> tuple[str, int]:
    """Private key blocks (PEM), found header first and closed within 6,000 characters."""
    out, i, n = [], 0, 0
    while begin := PEM_BEGIN.search(text, i):
        end = PEM_END.search(text, begin.end(), begin.end() + 6000)
        if not end:
            out.append(text[i:begin.end()])
            i = begin.end()
            continue
        out.append(text[i:begin.start()] + "[REDACTED:private_key]")
        i, n = end.end(), n + 1
    out.append(text[i:])
    return "".join(out), n


def card(number: str) -> bool:
    """15 to 19 digits, a card network's first digit, and a valid Luhn check digit."""
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    luhn = sum(d if i % 2 == 0 else (d * 2 - 9 if d > 4 else d * 2) for i, d in enumerate(digits[::-1]))
    return 15 <= len(digits) <= 19 and digits[0] in (2, 3, 4, 5, 6) and luhn % 10 == 0


PII = {
    "card": (r"(?<!\d)(?:\d[ -]?){14,18}\d(?!\d)", card),
    # 주민등록번호 and 외국인등록번호 (7th digit 5-8). No checksum: numbers issued since October 2020
    # end in random digits, so a failed check digit must never clear a match.
    "rrn": (r"(?<!\d)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])-?[1-8]\d{6}(?!\d)", None),
    "ssn": (r"(?<!\d)(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?!\d)", None),
    "email": (r"\b[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}\b", None),
    "phone": (r"(?<![\d-])(?:\+\d{1,3}[ -]?)?\(?\d{2,4}\)?[ -]?\d{3,4}[ -]\d{4}(?![\d-])", None),
}
PII = {name: (re.compile(p, re.ASCII), check) for name, (p, check) in PII.items()}

# Every way an answer can make a renderer fetch or link a URL: markdown images and links (inline
# and reference-style), media tags, and any URL anywhere else, including protocol-relative ones,
# bare www. hosts and script schemes.
IMAGE = re.compile(r"!\[([^\]]{0,500})\]\(\s*<?([^)\s>]{0,2000})>?[^)]{0,500}\)")
IMAGE_REF = re.compile(r"!\[[^\]]{0,500}\]\[([^\]]{1,100})\]")
REF_DEF = re.compile(r"(?m)^[ \t]{0,3}\[([^\]]{1,100})\]:[ \t]*<?([^\s>]{1,2000})>?")
MEDIA = re.compile(r"<(?:img|source|video|audio|iframe|embed|object|picture)\b[^>]{0,2000}>", re.I)
MEDIA_URL = re.compile(r"""\b(?:src|srcset|data|poster)\s*=\s*["']?([^"'>]{1,2000})""", re.I)
LINK = re.compile(r"(?<!!)\[([^\]]{1,500})\]\(\s*<?([^)\s>]{1,2000})>?[^)]{0,500}\)")
URL = re.compile(r"(?:\b(?:https?|ftp|wss?):)?//[^\s<>\"'()\[\]{}\\]{1,2000}|\bwww\.[^\s<>\"'()\[\]{}\\]{1,2000}"
                 r"|\b(?:javascript|vbscript):[^\s<>\"']{1,2000}", re.I)

INSTRUCTIONS = re.compile(
    r"(?im)^\W*(?:system|assistant|developer)\s*:"
    r"|\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|your\s+|the\s+){0,4}(?:previous|prior|above|earlier)\s+"
    r"(?:instructions|rules|prompts?)|\byou\s+are\s+now\b|\bnew\s+instructions?\s*:")


# ---------------------------------------------------------------- the guard

class Guard:
    refusal = "I can't help with that request."
    withheld = "I can't share that answer."

    def __init__(self, pii: tuple = ("card", "rrn", "ssn"), hosts: tuple = (),
                 classify: Callable[[str, str], list[Finding]] | None = None, classify_data: bool = False):
        self.pii = {name: PII[name] for name in pii}
        self.hosts = tuple(h.lower().rstrip(".") for h in hosts)
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
                if check and not check(m):
                    return m.group(0)
                found.append(Finding(rule, edit or action))
                return repl(m) if callable(repl) else repl
            text = pattern.sub(one, text)

        sub(TAGS, "hidden.tags", "strip", "")
        sub(INVISIBLE, "hidden.invisible", "strip", "")
        sub(SELECTORS, "hidden.selectors", "strip", "")
        if stage == "data":
            text, n = strip_blocks(text)
            found += [Finding("hidden.html", "strip")] * n
            if any(HIDDEN_STYLE.search(tag) for tag in TAG.findall(text)):
                found.append(Finding("hidden.styled", "flag"))  # no regex can find where it ends, so flag it
        text, n = redact_keys(text)
        found += [Finding("secret.private_key", edit or "redact")] * n
        for name, pattern in SECRETS.items():
            sub(pattern, f"secret.{name}", "redact", f"[REDACTED:{name}]" + ("@" if name == "url_password" else ""))
        for name, (pattern, check) in self.pii.items():
            sub(pattern, f"pii.{name}", "redact", f"[REDACTED:{name}]", check and (lambda m, c=check: c(m.group(0))))
        if stage in ("output", "egress"):
            images = {label.lower() for label in IMAGE_REF.findall(text)}
            sub(REF_DEF, "exfil.link", "strip", lambda m: f"[{m.group(1)}]: [link removed]",
                lambda m: not self._safe(m.group(2), image=m.group(1).lower() in images))
            sub(IMAGE, "exfil.image", "strip", "[image removed]", lambda m: not self._safe(m.group(2), image=True))
            sub(MEDIA, "exfil.image", "strip", "[image removed]", lambda m: not self._safe_media(m.group(0)))
            sub(LINK, "exfil.link", "strip", lambda m: f"{m.group(1)} [link removed]",
                lambda m: not self._safe(m.group(2)))
            sub(URL, "exfil.link", "strip", "[link removed]", lambda m: not self._safe(m.group(0)))
        if stage == "data" and INSTRUCTIONS.search(text):
            found.append(Finding("injection.suspected", "flag"))
        if self.classify and (stage in ("prompt", "output") or (stage == "data" and self.classify_data)):
            found += self.classify(text, stage)
        return Verdict(text, found)

    def _safe(self, url: str, image: bool = False) -> bool:
        """Relative links stay. Absolute ones need https, no user name, and a listed host (or a
        subdomain of one); images also need no query string, since that is where data rides out.
        Backslashes count as slashes, as they do in browsers."""
        url = url.strip().replace("\\", "/")
        if url.lower().startswith("www."):
            url = "https://" + url
        if not re.match(r"(?i)^(?:[a-z][a-z0-9+.-]*:|//)", url):
            return True
        parts = urllib.parse.urlsplit("https:" + url if url.startswith("//") else url)
        if parts.scheme.lower() != "https" or "@" in parts.netloc or (image and parts.query):
            return False
        host = (parts.hostname or "").rstrip(".").lower()
        return any(host == h or host.endswith("." + h) for h in self.hosts)

    def _safe_media(self, tag: str) -> bool:
        urls = [u for value in MEDIA_URL.findall(tag) for u in re.split(r"[\s,]+", value) if u and not u[0].isdigit()]
        return all(self._safe(u, image=True) for u in urls)


# ---------------------------------------------------------------- classifiers
# A classifier is classify(text, stage) -> list[Finding]; stage is "prompt", "data" or "output".
# Model names are configuration; check the current ones before relying on any default here.

class OpenAIModeration:
    """OpenAI moderation endpoint: text (and image) categories, flagged per category."""

    def __init__(self, model: str = "omni-moderation-latest", api_key: str | None = None,
                 url: str = "https://api.openai.com/v1/moderations"):
        self.model, self.url = model, url
        self.api_key = key("OPENAI_API_KEY", api_key)

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
