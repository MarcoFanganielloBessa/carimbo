"""carimbo command line."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import __version__
from .core import TYPES, CarimboError, Config, Vault, find_personal, init_vault, split_key

SESSION_ENV = ("CARIMBO_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID")


def session_id() -> str:
    return next((os.environ[v] for v in SESSION_ENV if os.environ.get(v)), "")


def state_dir() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "carimbo" / "seen"


def seen(session: str, ts: float | None = None) -> float:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / re.sub(r"[^\w-]", "_", session or "anon")
    if ts is not None:
        f.write_text(str(ts))
    return float(f.read_text()) if f.exists() else 0.0


def project_for(cfg: Config, cwd: str) -> str | None:
    parts = Path(cwd or ".").parts
    return next((p for folder, p in cfg.projects.items() if folder in parts), None)


def hook_output(event: str, context: str, notice: str | None = None) -> None:
    out = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}
    if notice:
        out["systemMessage"] = notice
    print(json.dumps(out, ensure_ascii=False))


def cmd_hook(v: Vault, which: str) -> None:
    """Claude Code hooks. session-start injects the project's state; prompt injects what other sessions stamped since."""
    data = json.load(sys.stdin)
    session, project = data.get("session_id", ""), project_for(v.cfg, data.get("cwd", ""))
    if not project or not (v.root / ".git").exists():
        return
    now = time.time()
    if which == "session-start":
        seen(session, now)
        body = v.state_text(project + ".")
        if body:
            hook_output("SessionStart",
                        f"Shared decision memory for `{project}` (carimbo vault at {v.root}). Do not reopen anything under "
                        "Decided without a new fact. When the user decides something or a status changes, stamp it right "
                        "away: `carimbo set <key> \"<text>\" --source \"<who, when>\"`.\n\n" + body)
        return
    since = seen(session)
    lines = v.changes_since(since, session, project) if since else []
    seen(session, now)
    if lines:
        hook_output("UserPromptSubmit", "Changed in the shared memory since your last message (another session stamped it):\n"
                    + "\n".join(lines), f"carimbo: {len(lines)} change(s) from another session")


def cmd_check(v: Vault, files: list[str], staged: bool) -> int:
    root = v.root
    if staged:
        out = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--name-only", "-z", "--diff-filter=ACM"],
                             capture_output=True, text=True).stdout  # -z: names with spaces or accents come unquoted
        files = [str(root / f) for f in out.split("\0") if f]
    bad = 0
    for f in map(Path, files):
        rel = f.relative_to(root) if f.is_absolute() and f.is_relative_to(root) else f
        if f.suffix != ".md" or not f.exists() or rel.parts[:1] == ("people",):
            continue
        for i, line in enumerate(f.read_text().splitlines(), 1):
            for kind, value in find_personal(line, v.cfg.allow):
                print(f"{rel}:{i}: {kind}: {value}")
                bad = 1
    if bad:
        print("refused: personal data in the vault. Remove it, or keep contacts in people/ only.", file=sys.stderr)
    return bad


def cmd_approve(v: Vault, raw: str):
    """A note proposed by an agent, approved by a human (for example in a task app): a ```carimbo JSON block."""
    m = re.search(r"```carimbo\s*\n(.*?)\n\s*```", raw, re.S)
    if not m:
        raise CarimboError("no ```carimbo block in the input")
    d = json.loads(m.group(1))
    same = v.get(d["key"])
    if same and same.text == d["text"]:  # the same approval read twice
        return same
    return v.stamp("set", d["key"], d["text"], type=d.get("type", "decision"), source=d.get("source", ""),
                   discarded=d.get("discarded", ""), links=d.get("links", []), session=d.get("session") or "approved")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="carimbo", description="Decision memory for AI agent teams, in Markdown and git.")
    p.add_argument("--vault", help="vault folder (default: $CARIMBO_VAULT or ~/carimbo)")
    p.add_argument("--version", action="version", version=f"carimbo {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a vault")
    s.add_argument("path", nargs="?")
    s.add_argument("--timezone", default="UTC")

    s = sub.add_parser("set", help="stamp a decision, status or pending question")
    s.add_argument("key")
    s.add_argument("text")
    s.add_argument("--type", choices=TYPES, default="decision")
    s.add_argument("--source", default="", help="who said it and when, e.g. 'Ana in #launch, 2026-11-10 18:30'")
    s.add_argument("--discarded", default="", help="the alternatives that lost, and why")
    s.add_argument("--links", default="", help="related keys, comma separated")

    s = sub.add_parser("end", help="take a key out of the current state (it moves to archive/)")
    s.add_argument("key")
    s.add_argument("reason")

    s = sub.add_parser("show", help="current state, optionally under a prefix")
    s.add_argument("prefix", nargs="?", default="")
    s.add_argument("--short", action="store_true")

    s = sub.add_parser("history", help="every version of one key")
    s.add_argument("key")

    sub.add_parser("index", help="rebuild INDEX.md and INDEX-SHORT.md")

    s = sub.add_parser("check", help="refuse personal data in notes (use as a pre-commit hook)")
    s.add_argument("files", nargs="*")
    s.add_argument("--staged", action="store_true")

    sub.add_parser("approve", help="stamp the ```carimbo block read from stdin")

    s = sub.add_parser("hook", help="Claude Code hooks (JSON on stdin)")
    s.add_argument("event", choices=("session-start", "prompt"))
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        if a.cmd == "init":
            path = init_vault(Path(a.path or a.vault or os.environ.get("CARIMBO_VAULT") or Path.home() / "carimbo"), a.timezone)
            print(f"vault ready at {path}")
            return 0
        v = Vault(Config.load(a.vault))
        if not (v.root / ".git").exists():
            if a.cmd == "hook":
                return 0  # hooks must never break a session
            raise CarimboError(f"no vault at {v.root}; run `carimbo init {v.root}` or set CARIMBO_VAULT")
        if a.cmd == "set":
            n = v.stamp("set", a.key, a.text, type=a.type, source=a.source, discarded=a.discarded,
                        links=[k.strip() for k in a.links.split(",") if k.strip()], session=session_id())
            print("stamped:", v.line(n))
        elif a.cmd == "end":
            v.stamp("end", a.key, a.reason, session=session_id())
            print(f"ended: `{a.key}`: {a.reason}")
        elif a.cmd == "show":
            print(v.state_text(a.prefix, short=a.short) or "Nothing stamped yet.")
        elif a.cmd == "history":
            split_key(a.key)
            for n in v.history(a.key):
                end = f" (ended: {n.extra['reason']})" if n.extra.get("reason") else ""
                print(datetime.fromtimestamp(n.ts, v.cfg.timezone).strftime("%Y-%m-%d %H:%M"), n.type, n.text + end)
        elif a.cmd == "index":
            v.write_index()
            print("INDEX.md and INDEX-SHORT.md rebuilt")
        elif a.cmd == "check":
            return cmd_check(v, a.files, a.staged)
        elif a.cmd == "approve":
            print("stamped:", v.line(cmd_approve(v, sys.stdin.read())))
        elif a.cmd == "hook":
            try:
                cmd_hook(v, a.event)
            except Exception as e:  # a broken hook must not block the agent
                print(f"carimbo hook: {e}", file=sys.stderr)
        return 0
    except CarimboError as e:
        print(f"carimbo: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
