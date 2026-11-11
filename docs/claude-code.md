# Claude Code

Two hooks connect every Claude Code session to the vault. The setup prompt in the [README](../README.md#quick-start) does everything on this page for you, after asking; this page is for doing it by hand.

| Hook | Command | What the session receives |
|---|---|---|
| `SessionStart` | `carimbo hook session-start` | The current state of its project: waiting, decided, status |
| `UserPromptSubmit` | `carimbo hook prompt` | Only what other sessions stamped since its last message, plus a one-line notice for you |

## 1. Map folders to projects

The hooks decide the project by a folder name in the session's working directory. In `carimbo.toml` at the root of the vault:

```toml
timezone = "America/Sao_Paulo"

[projects]
"acme-web" = "acme"      # any session under .../acme-web/... gets the acme.* state
"acme-infra" = "acme"
"blog" = "personal"
```

A session in a folder that is not listed gets nothing, so unrelated work stays clean.

## 2. Add the hooks

In `~/.claude/settings.json` (all projects) or `.claude/settings.json` (one repository):

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "carimbo --vault ~/carimbo hook session-start", "timeout": 10 }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "carimbo --vault ~/carimbo hook prompt", "timeout": 10 }] }
    ]
  }
}
```

Use the absolute path of `carimbo` (`command -v carimbo`) if Claude Code runs from a desktop app or an IDE, since those do not always load your shell's `PATH`. If the vault is not at `~/carimbo`, also add `"env": { "CARIMBO_VAULT": "/path/to/vault" }` to the same file, so `carimbo set` finds it inside every session.

The hooks never block a session: a missing vault, bad input or a git error prints to stderr and exits 0.

## 3. Tell the agent when to stamp

Add to `CLAUDE.md`:

```markdown
## Decisions
- The shared state of this project comes from carimbo at session start. Do not reopen anything under "Decided" without a new fact.
- When I decide something, or the status of a front changes, stamp it right away:
  `carimbo set <project>.<topic>.<subject> "<the decision in one or two sentences>" --source "<who, when>" --discarded "<what lost, why>"`
- A question that only I can answer: `--type pending`. Once answered, stamp the same key as a decision.
- Never write notes in the vault by hand, and never put emails, phone numbers or ID numbers in them.
```

## How the sync works

Each stamp is one commit whose body carries the session id (`Session: <id>`, taken from `CLAUDE_CODE_SESSION_ID`). The prompt hook reads `git log` since the last time this session was seen, skips its own commits, and reports the latest version of each key that another session changed. The last-seen time per session is kept in `~/.local/state/carimbo/seen/`.

A stamp made in the same second as the session start is reported once more on the first prompt. That is on purpose: a duplicate line costs less than a missed change.
