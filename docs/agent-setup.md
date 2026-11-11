# carimbo setup, for the agent

You are an AI agent with a shell, and the user asked you to set up carimbo. Follow these steps in order. Talk to the user in the language they wrote to you in. Keep messages short.

carimbo keeps one Markdown note per decision in a git folder (the vault). Hooks or a short instruction block make every agent session read the current decisions and stamp new ones. The project lives at https://github.com/MarcoFanganielloBessa/carimbo.

Ground rules for the whole setup:

- Ask before you edit any file of the user's agent configuration (`~/.claude/settings.json`, any `CLAUDE.md`, `AGENTS.md`, Cursor rules). Show the exact diff first and wait for an explicit yes.
- Never connect the vault to a public remote, and never create a public repository for it. A vault holds the team's decisions; it belongs in a private repository or on this machine only.
- Never put emails, phone numbers, CPF or SSN numbers in a note. carimbo refuses them anyway.
- If a step fails, stop, show the error and say what you would try next. Do not work around it silently.

## 1. Check where you are running

Run these and read the output:

```bash
uname -s; python3 --version; git --version; command -v uv pipx carimbo; echo "remote=${CLAUDE_CODE_REMOTE:-}"
```

- **No shell at all** (a chat app without a terminal): stop. Tell the user carimbo needs an agent that can run commands, such as Claude Code, Codex CLI or Cursor, and point them to the "Where it runs" section of the README.
- **`remote=true`** means you are Claude Code on the web, in a cloud VM. The vault and the hooks have to live on the user's own machine. Stop and tell the user to run this setup from Claude Code on their computer.
- **Windows outside WSL:** carimbo needs macOS or Linux. Suggest WSL and stop.
- **Python older than 3.11:** tell the user; `uv` can install a newer Python for the tool by itself, `pipx` cannot.
- **`carimbo` already on PATH:** run `carimbo --version`, tell the user, and reuse it.

## 2. Ask everything in one message

Send one message with these numbered questions and a suggested answer for each, then wait:

1. **Vault folder.** Suggest `~/carimbo`. If that folder already has a `carimbo.toml`, say so: you will reuse it, not recreate it.
2. **Timezone**, as an IANA name. Suggest the machine's own (`readlink /etc/localtime` on Linux and macOS ends with it, for example `America/Sao_Paulo`).
3. **Which project folder to map**, and the project name for it. Suggest the folder of the current working directory and its name in lowercase (`acme-web` → project `acme`). Several folders can share one project.
4. **A private git remote for the vault**, if they want sync between machines. Suggest none for now; it can be added later.

## 3. Install

Prefer `uv`; use `pipx` if that is what the machine has:

```bash
uv tool install git+https://github.com/MarcoFanganielloBessa/carimbo
# or
pipx install git+https://github.com/MarcoFanganielloBessa/carimbo
```

If neither `uv` nor `pipx` is installed, ask the user which one to install and use the official instructions (https://docs.astral.sh/uv/getting-started/installation/ or https://pipx.pypa.io/stable/installation/). Do not pipe an installer into a shell without their yes.

Then:

```bash
carimbo --version
command -v carimbo
```

If `carimbo` is not found, the tool folder is not on PATH yet: run `uv tool update-shell` (or `pipx ensurepath`) and tell the user to open a new terminal. Either way, keep the absolute path that `command -v carimbo` prints (usually `~/.local/bin/carimbo`); the hooks use it, because desktop apps and IDEs do not always load the shell's PATH.

## 4. Create the vault and map the project

```bash
carimbo init <vault> --timezone <timezone>
```

Edit `<vault>/carimbo.toml` and add the mapping under `[projects]`, one line per folder:

```toml
[projects]
"acme-web" = "acme"
```

The key is a folder name that appears anywhere in the session's working directory; the value is the project, which becomes the first part of every key (`acme.launch.date`). This file is inside the vault you just created, so you do not need to ask before editing it, but show the user the lines you added.

Commit it in the vault: `git -C <vault> commit -am "map projects"`.

## 5. A remote, only if the user asked for one

- Check that the repository is private before you add it. With GitHub and `gh`: `gh repo view <owner>/<repo> --json visibility` must say `PRIVATE`. Without `gh`, try `git ls-remote` on the HTTPS URL with credentials disabled (`GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote https://github.com/<owner>/<repo>`); if that succeeds, the repository is public and you must not use it.
- If they want a new repository and have `gh`: `gh repo create <name> --private`, after they say yes.
- Then `git -C <vault> remote add origin <url>` and `git -C <vault> push -u origin HEAD`. From now on every stamp is pushed.

## 6. Connect the agent

Do the part that matches you. Show the diff and wait for a yes before each file.

### Claude Code (CLI, Desktop app, VS Code or JetBrains)

All of them read hooks from `~/.claude/settings.json`. Back the file up first (`cp ~/.claude/settings.json ~/.claude/settings.json.before-carimbo` if it exists), then merge this in without removing anything that is already there. If `hooks.SessionStart` or `hooks.UserPromptSubmit` already exist, append to their arrays.

```json
{
  "env": { "CARIMBO_VAULT": "<absolute vault path>" },
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "<absolute carimbo path> --vault <absolute vault path> hook session-start", "timeout": 10 }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "<absolute carimbo path> --vault <absolute vault path> hook prompt", "timeout": 10 }] }
    ]
  }
}
```

`env.CARIMBO_VAULT` lets plain `carimbo set` in any session find the vault. Check the result is valid JSON (`python3 -m json.tool ~/.claude/settings.json >/dev/null`).

Then add the working rules (section 7) to the `CLAUDE.md` at the root of each mapped project folder, creating it if needed. Use the user-level `~/.claude/CLAUDE.md` only if the user asks for it, since that file applies to every project.

### Codex CLI, Cursor, or any other agent with a shell

These agents read the state at the start of each task instead of through hooks. Add the working rules (section 7) to `AGENTS.md` at the root of each mapped project folder (Codex and Cursor both read it), or to the agent's own instructions file if the user prefers. Write the full vault path into the commands (`carimbo --vault <vault> ...`), because these agents do not get `CARIMBO_VAULT` from anywhere.

Codex CLI also has `SessionStart` and `UserPromptSubmit` hooks with the same output format as Claude Code, but carimbo has not been tested with them. Do not configure them unless the user asks, and if they do, say it is untested.

## 7. The working rules block

Replace `<project>` and `<vault>`. In `CLAUDE.md` you can leave out `--vault <vault>`, since the hooks and `env` already cover it.

```markdown
## Decisions (carimbo)
- The current decisions for this project are in carimbo. Claude Code receives them at session start; any other agent runs `carimbo --vault <vault> show <project>.` before starting a task. Do not reopen anything under "Decided" without a new fact.
- When the user decides something, or the status of a front changes, stamp it right away and tell the user the key:
  `carimbo --vault <vault> set <project>.<topic>.<subject> "<the decision in one or two sentences>" --source "<who, when>" --discarded "<what lost, and why>"`
- A decision that changes: stamp the same key again. The old version goes to the archive by itself.
- A question only the user can answer: `--type pending`. Once answered, stamp the same key as a decision.
- Something that no longer applies: `carimbo --vault <vault> end <key> "<why>"`.
- "What did we decide about X?": `carimbo --vault <vault> show <project>.<topic>` and, for the changes over time, `carimbo --vault <vault> history <key>`.
- Never edit notes in the vault by hand. Never put emails, phone numbers or ID numbers in them.
```

## 8. Test it

Stamp a test note, read it back, and for Claude Code also run the hook by hand:

```bash
carimbo --vault <vault> set <project>.carimbo.setup "carimbo is connected to this project." --type status --source "<your agent name>, setup, <today>"
carimbo --vault <vault> show <project>.
echo '{"session_id":"setup-check","cwd":"<mapped project folder>"}' | <absolute carimbo path> --vault <vault> hook session-start
```

The hook must print JSON whose `additionalContext` contains the test note. Then take the test note out of the current state, so the vault starts clean (it stays in the history):

```bash
carimbo --vault <vault> end <project>.carimbo.setup "setup test"
```

## 9. Tell the user how it works from now on

Finish with a short message, in a few lines:

- what was installed and where the vault is, and whether it has a remote;
- which files you changed, and the backup of `settings.json` if you made one;
- that Claude Code picks up the hooks in the next session it opens (start a new one), and other agents read the state at the start of each task;
- how to use it: say "decided: …", "we changed …", "open question: …" or "drop …" and you stamp it; ask "what did we decide about …?" and you look it up.
