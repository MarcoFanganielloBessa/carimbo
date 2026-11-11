"""The vault: one Markdown note per key, old versions in archive/, a generated INDEX.md, one git commit per write."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TYPES = ("decision", "status", "pending")
FOLDERS = {"decision": "decisions", "status": "status", "pending": "pending"}
HEADINGS = {"pending": "Waiting for a decision", "decision": "Decided", "status": "Status"}
FIELDS = ("key", "type", "date", "source", "discarded", "replaces", "links", "session")
SEP = "\n\n---\n"  # separates the note text from the footer (discarded, source, links)
# Top-level folders that are not projects: free notes, agent inboxes, raw sources.
RESERVED = {"agents", "people", "sources", "templates", "notes", "archive", "assets"}
KEY_RE = re.compile(r"[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+")
SHORT_LIMIT = 150

# Personal data never goes into a note: the vault is pushed to git remotes and read by servers and models.
PERSONAL = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}",
    "phone": r"(?<![\w.])(?:\+\d{1,3}[\s.-]?)?\(?\d{2,3}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}(?![\w.])",
    "cpf": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}


class CarimboError(Exception):
    pass


@dataclass
class Config:
    vault: Path
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))
    projects: dict[str, str] = field(default_factory=dict)  # folder name in the session's cwd -> project
    allow: list[str] = field(default_factory=list)  # regexes for addresses that are not personal data
    reserved: set[str] = field(default_factory=lambda: set(RESERVED))
    sync: bool = True

    @classmethod
    def load(cls, vault: str | Path | None = None) -> "Config":
        root = Path(vault or os.environ.get("CARIMBO_VAULT") or Path.home() / "carimbo").expanduser()
        cfg = cls(vault=root)
        f = root / "carimbo.toml"
        if f.exists():
            d = tomllib.loads(f.read_text())
            cfg.timezone = ZoneInfo(d.get("timezone", "UTC"))
            cfg.projects = dict(d.get("projects", {}))
            cfg.allow = list(d.get("privacy", {}).get("allow", []))
            cfg.reserved |= set(d.get("reserved", []))
            cfg.sync = bool(d.get("sync", True))
        return cfg


def split_key(key: str) -> tuple[str, str]:
    """acme.launch.date -> ("acme", "launch-date")"""
    if not KEY_RE.fullmatch(key):
        raise CarimboError(f"invalid key: {key!r} (use project.topic.subject, lowercase, dots between parts)")
    project, _, rest = key.partition(".")
    return project, rest.replace(".", "-")


def find_personal(text: str, allow: list[str] = ()) -> list[tuple[str, str]]:
    found = []
    for kind, pattern in PERSONAL.items():
        for m in re.finditer(pattern, text):
            if not any(re.search(a, m.group(0)) for a in allow):
                found.append((kind, m.group(0)))
    return found


# ---------- note format ----------

def _scalar(v: str):
    """One frontmatter value. carimbo writes one JSON value per line; Obsidian and other editors may rewrite it as plain YAML."""
    v = v.strip()
    if v.startswith('"'):
        try:
            return json.loads(v)
        except ValueError:
            return v.strip('"')
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def parse_frontmatter(block: str) -> dict:
    """JSON per line or simple YAML: `k: v`, `k: [a, "b"]` and block lists (`k:` followed by `  - item`)."""
    out, current = {}, None
    for line in block.split("\n"):
        m = re.match(r"^(\w+):(?:\s+(.*))?$", line)
        if m:
            current, v = m.group(1), (m.group(2) or "").strip()
            if v.startswith("["):
                try:
                    out[current] = json.loads(v)
                except ValueError:
                    out[current] = [_scalar(i) for i in v.strip("[]").split(",") if i.strip()]
            else:
                out[current] = _scalar(v) if v or current != "links" else []
        elif current and re.match(r"^\s*-\s+", line):
            if not isinstance(out[current], list):
                out[current] = []
            out[current].append(_scalar(re.sub(r"^\s*-\s+", "", line)))
    return out


@dataclass
class Note:
    key: str
    type: str
    date: str
    text: str
    source: str = ""
    discarded: str = ""
    replaces: str = ""
    links: list[str] = field(default_factory=list)
    session: str = ""
    extra: dict = field(default_factory=dict)  # archived, reason
    path: Path | None = None

    @property
    def ts(self) -> float:
        return datetime.fromisoformat(self.date).timestamp()

    @property
    def slug(self) -> str:
        return split_key(self.key)[1]

    @classmethod
    def read(cls, path: Path) -> "Note":
        m = re.match(r"---\n(.*?)\n---\n(.*)", path.read_text(), re.S)
        if not m:
            raise CarimboError(f"{path}: no frontmatter")
        fm = parse_frontmatter(m.group(1))
        known = {k: fm.pop(k) for k in list(fm) if k in FIELDS}
        links = known.pop("links", []) or []
        return cls(text=m.group(2).split(SEP)[0].strip(), links=links if isinstance(links, list) else [links],
                   extra=fm, path=path, **{k: str(v) for k, v in known.items()})

    def render(self, wiki_links: list[str]) -> str:
        values = {k: getattr(self, k) for k in FIELDS} | self.extra
        fm = "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in values.items())
        footer = [f"**{label}:** {v}" for label, v in (("Discarded", self.discarded), ("Source", self.source),
                                                      ("Replaces", self.replaces), ("Ended", self.extra.get("reason")))
                  if v]
        if wiki_links:
            footer.append("Linked to: " + " · ".join(wiki_links))
        return f"---\n{fm}\n---\n{self.text.strip()}" + (SEP + "\n\n".join(footer) if footer else "") + "\n"


# ---------- the vault ----------

class Vault:
    def __init__(self, config: Config):
        self.cfg = config
        self.root = config.vault

    # git
    def git(self, *args: str, ok: bool = False) -> subprocess.CompletedProcess:
        r = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, timeout=60)
        if r.returncode and not ok:
            raise CarimboError(f"git {args[0]} failed: {r.stderr.strip()}")
        return r

    def has_remote(self) -> bool:
        return bool(self.git("remote", ok=True).stdout.strip())

    @contextmanager
    def lock(self):
        import fcntl
        with open(self.root / ".git" / "carimbo.lock", "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def push(self) -> None:
        for _ in range(2):
            if self.git("push", "-q", "origin", "HEAD", ok=True).returncode == 0:
                return
            if self.git("pull", "-q", "--rebase", ok=True).returncode:
                self.git("rebase", "--abort", ok=True)
                break
        print("carimbo: push failed; the commit stays local and goes up with the next write", file=sys.stderr)

    def commit(self, subject: str, body: str) -> None:
        self.git("add", "-A")
        if self.git("diff", "--cached", "--quiet", ok=True).returncode:
            self.git("commit", "-q", "-m", subject, "-m", body)
            if self.cfg.sync and self.has_remote():
                self.push()

    # reading
    def projects(self) -> list[Path]:
        return sorted(d for d in self.root.iterdir()
                      if d.is_dir() and not d.name.startswith(".") and d.name not in self.cfg.reserved)

    def notes(self, *folders: str) -> list[Note]:
        return [Note.read(f) for d in self.projects() for sub in folders for f in sorted((d / sub).glob("*.md"))]

    def current(self, prefix: str = "") -> list[Note]:
        return [n for n in self.notes(*FOLDERS.values()) if n.key.startswith(prefix)]

    def get(self, key: str) -> Note | None:
        return next((n for n in self.current(split_key(key)[0] + ".") if n.key == key), None)

    def history(self, key: str) -> list[Note]:
        def order(n: Note):  # versions stamped in the same second: archive time, then the -2, -3 suffix
            m = re.search(r"-(\d+)$", n.path.stem) if n.path and n.path.parent.name == "archive" else None
            suffix = int(m.group(1)) if m and n.path.stem.count("--") and len(m.group(1)) < 4 else 1
            return n.ts, n.extra.get("archived", "9999"), suffix
        return sorted((n for n in [*self.notes("archive"), *self.current()] if n.key == key), key=order)

    def wiki_links(self, n: Note) -> list[str]:
        project = split_key(n.key)[0]
        topic = n.key.split(".")[1]
        own = [f"[[{topic}]]"] if (self.root / project / "topics" / f"{topic}.md").exists() else []
        return own + [f"[[{split_key(k)[1]}]]" for k in n.links]

    def write_note(self, path: Path, n: Note) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(n.render(self.wiki_links(n)))

    # writing
    def stamp(self, op: str, key: str, text: str, *, type: str = "decision", source: str = "", discarded: str = "",
              links: list[str] | None = None, session: str = "", ts: float | None = None) -> Note | None:
        """op "set" writes or replaces the note (the old one moves to archive/); op "end" archives it with a reason."""
        project, slug = split_key(key)
        if type not in TYPES:
            raise CarimboError(f"invalid type: {type} (use {', '.join(TYPES)})")
        hits = find_personal(" ".join([text, source, discarded]), self.cfg.allow)
        if hits:
            raise CarimboError("refused: the text has personal data (" + ", ".join(k for k, _ in hits)
                               + "); keep emails, phones and ID numbers out of the vault")
        links = links or []
        for k in links:
            split_key(k)
        ts = ts or time.time()
        tz = self.cfg.timezone
        with self.lock():
            if self.cfg.sync and self.has_remote():
                self.git("pull", "-q", "--rebase", ok=True)
            old = self.get(key)
            if op == "end" and not old:
                raise CarimboError(f"{key} is not in the current state")
            archived = None
            if old:
                base = f"{slug}--{datetime.fromtimestamp(old.ts, tz):%Y-%m-%d-%H%M%S}"
                archived, i = self.root / project / "archive" / f"{base}.md", 1
                while archived.exists():  # two versions in the same second
                    i += 1
                    archived = archived.with_name(f"{base}-{i}.md")
                old.extra["archived"] = datetime.fromtimestamp(ts, tz).isoformat(timespec="seconds")
                if op == "end":
                    old.extra["reason"] = text
                self.write_note(archived, old)
                old.path.unlink()
            new = None
            if op == "set":
                new = Note(key=key, type=type, date=datetime.fromtimestamp(ts, tz).isoformat(timespec="seconds"),
                           text=text, source=source, discarded=discarded, links=links, session=session,
                           replaces=f"[[{archived.stem}]]" if archived else "")
                self.write_note(self.root / project / FOLDERS[type] / f"{slug}.md", new)
                new.path = self.root / project / FOLDERS[type] / f"{slug}.md"
            self.write_index()
            self.commit(f"{op} {key}", f"Session: {session}" + (f"\nReason: {text}" if op == "end" else ""))
        return new

    # index
    def line(self, n: Note, wiki: bool = False, short: bool = False) -> str:
        day = datetime.fromtimestamp(n.ts, self.cfg.timezone).strftime("%Y-%m-%d")
        label = f"[[{n.slug}]]" if wiki else f"`{n.key}`"
        body = n.text.replace("\n", " ")
        if short:
            if len(body) > SHORT_LIMIT:
                body = body[:SHORT_LIMIT].rsplit(" ", 1)[0] + "…"
            return f"- {label} ({day}): {body}"
        s = f"- {label} ({day}): {body}"
        if n.discarded:
            s += f" · discarded: {n.discarded}"
        if n.source:
            s += f" · source: {n.source}"
        return s

    def state_text(self, prefix: str = "", wiki: bool = False, short: bool = False) -> str:
        notes = sorted(self.current(prefix), key=lambda n: n.key)
        blocks = []
        for t in ("pending", "decision", "status"):
            lines = [self.line(n, wiki, short) for n in notes if n.type == t]
            if lines:
                blocks.append(f"### {HEADINGS[t]}\n" + "\n".join(lines))
        return "\n\n".join(blocks)

    def write_index(self) -> None:
        for name, short in (("INDEX.md", False), ("INDEX-SHORT.md", True)):
            parts = [f"# {'Short index' if short else 'Index'}\n\nGenerated by carimbo. Do not edit by hand: "
                     "change a note with `carimbo set` or `carimbo end`."]
            for d in self.projects():
                body = self.state_text(d.name + ".", wiki=True, short=short) or "Nothing stamped yet."
                if not short:
                    n_archive = len(list((d / "archive").glob("*.md")))
                    body += f"\n\nArchive: {n_archive} older versions in `{d.name}/archive/`."
                parts.append(f"## {d.name}\n\n{body}")
            (self.root / name).write_text("\n\n".join(parts) + "\n")

    # what other sessions changed
    def changes_since(self, since: float, session: str, project: str) -> list[str]:
        latest: dict[str, tuple[str, str]] = {}
        log = self.git("log", f"--since=@{int(since)}", "--format=%ct%x1f%s%x1f%b%x1e", ok=True).stdout
        for block in log.split("\x1e"):
            if not block.strip():
                continue
            ct, subject, body = block.strip("\n").split("\x1f")
            op, _, key = subject.partition(" ")
            who = (re.search(r"^Session: (.*)$", body, re.M) or [None, ""])[1].strip()
            if int(ct) + 1 > since and op in ("set", "end") and key.startswith(project + ".") and who != session:
                latest.setdefault(key, (op, body))  # git log is newest first
        live = {n.key: n for n in self.current(project + ".")}
        out = []
        for key, (op, body) in sorted(latest.items()):
            if op == "set" and key in live:
                out.append(self.line(live[key]))
            elif op == "end":
                out.append(f"- `{key}` ended: {(re.search(r'^Reason: (.*)$', body, re.M) or [None, ''])[1]}")
        return out


def init_vault(path: Path, timezone: str = "UTC") -> Path:
    path = path.expanduser()
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        subprocess.run(["git", "init", "-q", str(path)], check=True)
    files = {
        "carimbo.toml": TEMPLATE_TOML.replace("{tz}", timezone),
        "agents/README.md": AGENTS_README,
        ".gitignore": ".obsidian/workspace*\n.DS_Store\n.trash/\n",
    }
    for rel, content in files.items():
        f = path / rel
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
    hook = path / ".git" / "hooks" / "pre-commit"
    if not hook.exists():
        hook.write_text(PRE_COMMIT)
        hook.chmod(0o755)
    v = Vault(Config.load(path))
    v.write_index()
    v.git("add", "-A")
    if v.git("diff", "--cached", "--quiet", ok=True).returncode:
        v.git("commit", "-q", "-m", "carimbo init", "-m", "Session: init")
    return path


PRE_COMMIT = """#!/bin/sh
# carimbo: refuse personal data in staged notes
if command -v carimbo >/dev/null 2>&1; then
  exec carimbo --vault "$(git rev-parse --show-toplevel)" check --staged
fi
echo "carimbo is not on PATH; personal-data check skipped" >&2
"""

TEMPLATE_TOML = '''# carimbo vault settings
timezone = "{tz}"

# Which project a coding session belongs to, by a folder name in its working directory.
# The hooks only inject the state of that project.
[projects]
# "acme-web" = "acme"

[privacy]
# Regexes for addresses that are allowed in notes (for example your own system mailbox).
allow = []
'''

AGENTS_README = """# agents/

One folder per agent (`agents/designer/`, `agents/reviewer/` …). Each agent writes freely only in its own folder:
that is its short-term memory. The archivist reads all of them, promotes what matters to decisions with
`carimbo set`, and links notes with [[wiki links]].
"""
