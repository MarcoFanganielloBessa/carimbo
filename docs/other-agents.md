# Other agents

Any agent that can run a shell command can use carimbo: Codex, Cursor, Aider, OpenBot agents, scripts on a server. Without hooks, the agent reads the state itself at the start of a task.

Paste this into `AGENTS.md`, the agent's instructions or its system prompt, with your vault path and project:

```markdown
## Shared decisions (carimbo)
- Before you start a task, run `carimbo --vault ~/carimbo show acme.` and treat everything under "Decided" as settled unless you have a new fact.
- When the user decides something, stamp it: `carimbo --vault ~/carimbo set acme.<topic>.<subject> "<decision>" --source "<who, when>"`.
- A question only the user can answer: `--type pending`.
- Your own working notes go in `agents/<your-name>/` in the vault. Do not edit notes under the project folders by hand.
```

For a small context window, use `carimbo show acme. --short`: one line per key, cut at 150 characters.

## Agents that propose, people that approve

When an agent should not decide on its own, it can write the decision as a block in a task, a pull request or a message:

````markdown
```carimbo
{"key": "acme.ads.budget", "text": "Daily budget stays at 300 until the first sales report.", "source": "Ana, approved in the task app", "type": "decision"}
```
````

When a person approves it, a script pipes the text to `carimbo approve`. Reading the same approval twice does not stamp it twice.

## Several machines

Give the vault a git remote. Each stamp pulls with rebase, commits and pushes; a failed push stays local and goes up with the next stamp. A read-only server (a dashboard, a bot) can `git pull` the vault on a timer and read `INDEX.md` or the notes directly.
