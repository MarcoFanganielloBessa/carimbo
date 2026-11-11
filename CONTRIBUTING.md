# Contributing

- Keep it small: standard library only, Python 3.11+.
- Every change comes with a test in `tests/`. Run `python3 -m unittest discover -s tests`.
- The on-disk format is a contract. A change to frontmatter fields, folder names or commit messages needs a migration note in `CHANGELOG.md`.
- Never add real decisions, names or contact details to examples or tests.
