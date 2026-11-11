import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from carimbo import cli  # noqa: E402
from carimbo.core import CarimboError, Config, Note, Vault, find_personal, init_vault, parse_frontmatter, split_key  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def run(*argv, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), mock.patch("sys.stdin", io.StringIO(stdin)):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {**GIT_ENV, "XDG_STATE_HOME": tempfile.mkdtemp()})
        self.env.start()
        self.tmp = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", "--bare", str(self.tmp / "remote.git")], check=True)
        subprocess.run(["git", "clone", "-q", str(self.tmp / "remote.git"), str(self.tmp / "v")], check=True,
                       capture_output=True)
        init_vault(self.tmp / "v", "America/Sao_Paulo")
        (self.tmp / "v" / "carimbo.toml").write_text(
            'timezone = "America/Sao_Paulo"\n[projects]\n"acme-web" = "acme"\n[privacy]\nallow = ["@acme\\\\.dev"]\n')
        self.v = Vault(Config.load(self.tmp / "v"))
        (self.v.root / "acme" / "topics").mkdir(parents=True)
        (self.v.root / "acme" / "topics" / "launch.md").write_text("# launch\n")

    def tearDown(self):
        self.env.stop()

    def remote_commits(self):
        r = subprocess.run(["git", "-C", str(self.tmp / "remote.git"), "rev-list", "--count", "HEAD"],
                           capture_output=True, text=True)
        return int(r.stdout or 0)


class TestKeysAndPrivacy(unittest.TestCase):
    def test_split_key(self):
        self.assertEqual(split_key("acme.launch.date"), ("acme", "launch-date"))
        for bad in ("acme", "Acme.x", "acme..x", "acme.x y"):
            with self.assertRaises(CarimboError):
                split_key(bad)

    def test_personal_data(self):
        self.assertTrue(find_personal("write to ana@example.com"))
        self.assertTrue(find_personal("call (11) 98765-4321"))
        self.assertTrue(find_personal("call +55 11 98765 4321"))
        self.assertTrue(find_personal("cpf 123.456.789-09"))
        self.assertFalse(find_personal("bot@acme.dev reports", allow=[r"@acme\.dev"]))
        for fine in ("launch on 2026-11-16 at 12:00", "version 0.1.0", "R$ 1.234,56", "lot 2 at 18h30"):
            self.assertFalse(find_personal(fine), fine)


class TestFrontmatter(unittest.TestCase):
    def test_reads_json_lines_and_rewritten_yaml(self):
        for block in ('key: acme.x.t\ntype: decision\ndate: 2026-11-02T18:48:17-03:00\nsource: Ana, 02/11: "go"\n'
                      'links:\n  - acme.a.b\n  - "acme.c.d"\nsession: 7e5f9979',
                      'key: "acme.x.t"\ntype: "decision"\ndate: "2026-11-02T18:48:17-03:00"\n'
                      'source: \'Ana, 02/11: "go"\'\nlinks: ["acme.a.b", "acme.c.d"]\nsession: "7e5f9979"'):
            f = parse_frontmatter(block)
            self.assertEqual(f["key"], "acme.x.t")
            self.assertEqual(f["source"], 'Ana, 02/11: "go"')
            self.assertEqual(f["links"], ["acme.a.b", "acme.c.d"])
            self.assertEqual(f["session"], "7e5f9979")
        self.assertEqual(parse_frontmatter("key: a.b\nlinks: []")["links"], [])
        self.assertEqual(parse_frontmatter("key: a.b\nlinks:")["links"], [])
        self.assertEqual(parse_frontmatter("session: 12345678")["session"], "12345678")


class TestVault(Base):
    def test_set_replace_end(self):
        t0 = time.time() - 5
        self.v.stamp("set", "acme.launch.date", "Nov 16", source="Ana, kickoff", session="A")
        self.assertTrue((self.v.root / "acme/decisions/launch-date.md").exists())
        n = self.v.stamp("set", "acme.launch.date", "Nov 18", type="pending", links=["acme.launch.venue"], session="A")
        self.assertFalse((self.v.root / "acme/decisions/launch-date.md").exists())
        self.assertTrue(n.replaces.startswith("[[launch-date--"))
        note = Note.read(self.v.root / "acme/pending/launch-date.md")
        self.assertEqual((note.text, note.links), ("Nov 18", ["acme.launch.venue"]))
        self.assertIn("[[launch]] · [[launch-venue]]", note.path.read_text())
        self.assertIn("[[launch-date]]", (self.v.root / "INDEX.md").read_text())
        self.assertIn("[[launch-date]]", (self.v.root / "INDEX-SHORT.md").read_text())
        self.assertEqual(self.v.changes_since(t0, "B", "acme"), [self.v.line(note)])
        self.assertEqual(self.v.changes_since(t0, "A", "acme"), [])
        self.v.stamp("end", "acme.launch.date", "moved to 2027", session="A")
        self.assertEqual(self.v.current("acme."), [])
        self.assertEqual(len(list((self.v.root / "acme/archive").glob("launch-date--*.md"))), 2)
        self.assertEqual(self.v.changes_since(t0, "B", "acme"), ["- `acme.launch.date` ended: moved to 2027"])
        self.assertEqual([h.text for h in self.v.history("acme.launch.date")], ["Nov 16", "Nov 18"])
        self.assertEqual(self.remote_commits(), 4)  # init + 3 stamps, all pushed

    def test_refuses_personal_data_and_bad_input(self):
        for kwargs in ({"text": "send it to ana@example.com"}, {"text": "ok", "source": "call 11 98765-4321"}):
            with self.assertRaises(CarimboError):
                self.v.stamp("set", "acme.x.y", **kwargs)
        with self.assertRaises(CarimboError):
            self.v.stamp("set", "acme.x.y", "ok", type="idea")
        with self.assertRaises(CarimboError):
            self.v.stamp("end", "acme.x.y", "never existed")
        self.assertEqual(self.v.current(), [])

    def test_reserved_folders_are_not_projects(self):
        self.assertEqual([p.name for p in self.v.projects()], ["acme"])


class TestCli(Base):
    def test_commands(self):
        vault = str(self.v.root)
        self.assertEqual(run("--vault", vault, "set", "acme.launch.date", "Nov 16", "--discarded", "Nov 9: too early")[0], 0)
        code, out, _ = run("--vault", vault, "show", "acme.")
        self.assertIn("`acme.launch.date`", out)
        self.assertIn("discarded: Nov 9: too early", out)
        self.assertEqual(run("--vault", vault, "set", "acme.launch.date", "Nov 18")[0], 0)
        self.assertEqual(run("--vault", vault, "history", "acme.launch.date")[1].count("decision"), 2)
        code, _, err = run("--vault", vault, "set", "acme.x.y", "mail ana@example.com")
        self.assertEqual(code, 1)
        self.assertIn("personal data", err)
        self.assertEqual(run("--vault", str(self.tmp / "nope"), "show")[0], 1)

    def test_approve_is_idempotent(self):
        block = '```carimbo\n{"key": "acme.launch.lineup", "text": "Announce at noon"}\n```'
        self.assertEqual(run("--vault", str(self.v.root), "approve", stdin=block)[0], 0)
        self.assertEqual(run("--vault", str(self.v.root), "approve", stdin=block)[0], 0)
        self.assertEqual(len(self.v.history("acme.launch.lineup")), 1)

    def test_check(self):
        (self.v.root / "acme" / "notes.md").write_text("ping ana@example.com\n")
        (self.v.root / "people").mkdir()
        (self.v.root / "people" / "ana.md").write_text("ana@example.com\n")
        code, out, _ = run("--vault", str(self.v.root), "check", str(self.v.root / "acme/notes.md"),
                           str(self.v.root / "people/ana.md"))
        self.assertEqual(code, 1)
        self.assertIn("acme/notes.md:1: email", out)
        self.assertNotIn("people", out)

    def test_check_staged_names_with_spaces_and_accents(self):
        f = self.v.root / "notes" / "reunião de lançamento.md"
        f.parent.mkdir()
        f.write_text("ligar para ana@example.com\n")
        self.v.git("add", "-A")
        code, out, _ = run("--vault", str(self.v.root), "check", "--staged")
        self.assertEqual(code, 1)
        self.assertIn("reunião de lançamento.md:1: email", out)

    def test_init_refuses_unknown_timezone(self):
        code, _, err = run("init", str(self.tmp / "tz"), "--timezone", "Sao Paulo")
        self.assertEqual(code, 1)
        self.assertIn("unknown timezone", err)
        self.assertFalse((self.tmp / "tz").exists())

    def test_init_without_git_identity(self):
        home = Path(tempfile.mkdtemp())
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), GIT_CONFIG_NOSYSTEM="1",
                   EMAIL="", PYTHONPATH=str(Path(__file__).resolve().parent.parent / "src"))
        r = subprocess.run([sys.executable, "-m", "carimbo", "init", str(home / "v")], env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, "-m", "carimbo", "--vault", str(home / "v"), "set", "acme.x.y", "ok"],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_hooks(self):
        vault = str(self.v.root)
        self.v.stamp("set", "acme.launch.date", "Nov 16", session="A")
        time.sleep(1.1)  # a stamp in the same second as the session start is reported again, on purpose
        start = json.dumps({"session_id": "B", "cwd": "/home/x/code/acme-web/src"})
        _, out, _ = run("--vault", vault, "hook", "session-start", stdin=start)
        ctx = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(ctx["hookEventName"], "SessionStart")
        self.assertIn("Nov 16", ctx["additionalContext"])
        self.assertEqual(run("--vault", vault, "hook", "prompt", stdin=start)[1], "")
        cli.seen("B", time.time() - 5)
        self.v.stamp("set", "acme.launch.date", "Nov 18", session="A")
        _, out, _ = run("--vault", vault, "hook", "prompt", stdin=start)
        self.assertIn("Nov 18", json.loads(out)["hookSpecificOutput"]["additionalContext"])
        other = json.dumps({"session_id": "C", "cwd": "/home/x/elsewhere"})
        self.assertEqual(run("--vault", vault, "hook", "session-start", stdin=other)[1], "")
        self.assertEqual(run("--vault", str(self.tmp / "nope"), "hook", "prompt", stdin=start)[0], 0)
        self.assertEqual(run("--vault", vault, "hook", "prompt", stdin="not json")[0], 0)


if __name__ == "__main__":
    unittest.main()
