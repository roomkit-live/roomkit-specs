from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traceability._git import GitReader
from traceability.references import git_text


class GitFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q")

    def git(self, repo: Path, *args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], text=True
        ).strip()

    def commit(self, repo: Path) -> str:
        self.git(repo, "add", ".")
        self.git(
            repo,
            "-c",
            "user.name=Conformance Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "fixture",
        )
        return self.git(repo, "rev-parse", "HEAD")


class GitReaderTests(GitFixture):
    def test_binary_framing_and_text_conversion_match_git_show(self) -> None:
        bodies = {
            "empty": b"",
            "unix": b"  x\n\ny  \n",
            "windows": b"a\r\nb\rc\n",
            "nul": b"x\0y\n",
            "unicode": "é😀\r\n水".encode(),
            "large": ("😀\x00\r\nz" * 50_000).encode(),
            "space tab\t: é": b"named\n",
            "line\nbreak": b"line name",
            "carriage\rreturn": b"CR name",
        }
        for name, body in bodies.items():
            (self.repo / name).write_bytes(body)
        (self.repo / "link").symlink_to("unix")
        commit = self.commit(self.repo)
        with GitReader() as reader:
            for name in [*bodies, "link", "", "unix"]:
                with self.subTest(name=name):
                    self.assertEqual(
                        reader.read(self.repo, commit, name),
                        git_text(self.repo, commit, name),
                    )

    def test_commits_repositories_and_dirty_checkouts_are_distinct(self) -> None:
        path = self.repo / "value"
        path.write_text("first")
        first = self.commit(self.repo)
        path.write_text("second")
        second = self.commit(self.repo)
        path.write_text("dirty")
        other = self.root / "other"
        other.mkdir()
        self.git(other, "init", "-q")
        (other / "value").write_text("other")
        other_commit = self.commit(other)
        children = []
        popen = subprocess.Popen

        def start(*args, **kwargs):
            child = popen(*args, **kwargs)
            children.append(child)
            return child

        with patch("traceability._git.subprocess.Popen", side_effect=start):
            for _ in range(2):
                with GitReader() as reader:
                    for _ in range(100):
                        self.assertEqual(
                            reader.read(self.repo, first, "value"), "first"
                        )
                        self.assertEqual(
                            reader.read(self.repo, second, "value"), "second"
                        )
                        self.assertEqual(
                            reader.read(other, other_commit, "value"), "other"
                        )
                for child in children:
                    self.assertEqual(child.poll(), 0)
                    self.assertTrue(child.stdin.closed)
                    self.assertTrue(child.stdout.closed)
        self.assertEqual(len(children), 4, "one child per repository and validation")

    def test_missing_object_or_path_does_not_desynchronize_the_next_read(self) -> None:
        (self.repo / "value").write_text("ok")
        commit = self.commit(self.repo)
        with GitReader() as reader:
            for revision, path in [(commit, "absent"), ("0" * 40, "value")]:
                with self.subTest(revision=revision, path=path):
                    with self.assertRaises(ValueError) as batch:
                        reader.read(self.repo, revision, path)
                    with self.assertRaises(ValueError) as old:
                        git_text(self.repo, revision, path)
                    self.assertEqual(str(batch.exception), str(old.exception))
                    self.assertEqual(reader.read(self.repo, commit, "value"), "ok")

    def test_guards_run_before_starting_git_and_reader_is_lazy(self) -> None:
        with (
            patch("traceability._git.subprocess.Popen") as start,
            GitReader() as reader,
        ):
            for commit, path in [
                ("HEAD", "file"),
                ("a" * 40, "/file"),
                ("a" * 40, "a/../file"),
                ("A" * 40, "file"),
            ]:
                with (
                    self.subTest(commit=commit, path=path),
                    self.assertRaises(ValueError),
                ):
                    reader.read(self.repo, commit, path)
            start.assert_not_called()
        with self.assertRaisesRegex(ValueError, "closed"):
            reader.read(self.repo, "a" * 40, "file")

    def test_nul_path_uses_the_same_refusal_as_git_show(self) -> None:
        with GitReader() as reader:
            for read in [reader.read, git_text]:
                with self.assertRaisesRegex(ValueError, "embedded null"):
                    read(self.repo, "a" * 40, "bad\0path")

    def test_unavailable_repository_keeps_the_source_in_its_error(self) -> None:
        for repo in [self.root, self.root / "absent"]:
            with self.subTest(repo=repo), GitReader() as reader:
                with self.assertRaises(ValueError) as batch:
                    reader.read(repo, "a" * 40, "source")
                with self.assertRaises(ValueError) as old:
                    git_text(repo, "a" * 40, "source")
                self.assertEqual(str(batch.exception), str(old.exception))

    def test_git_exiting_before_the_first_request_keeps_the_same_error(self) -> None:
        popen = subprocess.Popen

        def already_exited(*args, **kwargs):
            child = popen(*args, **kwargs)
            self.assertEqual(child.wait(timeout=5), 128)
            return child

        for repo in [self.root, self.root / "absent"]:
            with self.subTest(repo=repo), GitReader() as reader:
                with patch(
                    "traceability._git.subprocess.Popen", side_effect=already_exited
                ):
                    with self.assertRaises(ValueError) as batch:
                        reader.read(repo, "a" * 40, "source")
                with self.assertRaises(ValueError) as old:
                    git_text(repo, "a" * 40, "source")
                self.assertEqual(str(batch.exception), str(old.exception))

    def test_undecodable_blob_fails_instead_of_changing_a_fingerprint(self) -> None:
        (self.repo / "bad").write_bytes(b"\xff")
        (self.repo / "good").write_text("ok")
        commit = self.commit(self.repo)
        with GitReader() as reader:
            for read in [reader.read, git_text]:
                with self.assertRaises(UnicodeDecodeError):
                    read(self.repo, commit, "bad")
            self.assertEqual(reader.read(self.repo, commit, "good"), "ok")

    def test_exception_reaps_all_children_and_preserves_the_original_error(
        self,
    ) -> None:
        (self.repo / "value").write_text("ok")
        commit = self.commit(self.repo)
        children = []
        popen = subprocess.Popen

        def start(*args, **kwargs):
            child = popen(*args, **kwargs)
            children.append(child)
            return child

        with patch("traceability._git.subprocess.Popen", side_effect=start):
            with self.assertRaisesRegex(KeyboardInterrupt, "caller interrupted"):
                with GitReader() as reader:
                    reader.read(self.repo, commit, "value")
                    raise KeyboardInterrupt("caller interrupted")
        self.assertEqual(children[0].poll(), 0)
        self.assertTrue(children[0].stdin.closed)
        self.assertTrue(children[0].stdout.closed)


if __name__ == "__main__":
    unittest.main()
