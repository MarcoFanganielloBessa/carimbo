# Vault layout and note format

```
~/carimbo/
  carimbo.toml            settings: timezone, folder-to-project map, privacy allow list
  INDEX.md                generated: the current state of every project
  INDEX-SHORT.md          generated: one line per key
  acme/                   a project (any top folder that is not reserved)
    decisions/            what is decided
    status/               where each front stands
    pending/              questions waiting for a person
    archive/              every replaced or ended version, with its date
    topics/               optional: one note per topic, linked from its keys
  agents/<name>/          each agent's free notes (short-term memory)
  people/                 the only place contact details may live
  notes/  sources/        anything else; carimbo does not touch them
```

Reserved top folders, which are never projects: `agents`, `people`, `sources`, `templates`, `notes`, `archive`, `assets`, plus anything listed under `reserved = [...]` in `carimbo.toml`.

## Keys

`project.topic.subject`, lowercase letters, digits and hyphens, at least two parts. The first part is the project folder; the rest becomes the file name with dots turned into hyphens. `acme.launch.date` → `acme/decisions/launch-date.md`.

If `acme/topics/launch.md` exists, every `acme.launch.*` note links to it, so the Obsidian graph groups decisions by topic.

## Types

| Type | Folder | Use it for |
|---|---|---|
| `decision` | `decisions/` | Something settled that agents must follow |
| `status` | `status/` | Where a front stands now (a fact that will change) |
| `pending` | `pending/` | A question only a person can answer |

Changing the type of a key moves it: the pending question goes to the archive and the decision takes its place.

## Frontmatter

| Field | Meaning |
|---|---|
| `key` | The key |
| `type` | `decision`, `status` or `pending` |
| `date` | When it was stamped, ISO 8601 in the vault's timezone |
| `source` | Who said it and when |
| `discarded` | Alternatives that lost, and why |
| `replaces` | Wiki link to the archived version it replaced |
| `links` | Related keys |
| `session` | The agent session that stamped it |
| `archived`, `reason` | Only in `archive/`: when it left the current state and, for `end`, why |

Each value is written as JSON on its own line, which any YAML reader accepts. The reader also accepts the plain YAML that Obsidian writes when you edit properties in its UI.

## Commits

One commit per stamp, subject `set <key>` or `end <key>`, body `Session: <id>` (and `Reason: …` for `end`). `git log -- acme/` is the full history of a project; `carimbo history <key>` is the history of one key.
