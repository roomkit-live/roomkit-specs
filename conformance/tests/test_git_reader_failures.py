from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traceability._git import GitReader


class GitReaderFailureTests(unittest.TestCase):
    def run_peer(self, script: str, operation) -> None:
        children = []
        popen = subprocess.Popen

        def start(*args, **kwargs):
            child = popen([sys.executable, "-c", script], **kwargs)
            children.append(child)
            return child

        with patch("traceability._git.subprocess.Popen", side_effect=start):
            operation()
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stdin.closed)
        self.assertTrue(children[0].stdout.closed)

    def test_invalid_or_incomplete_frames_never_return_a_source(self) -> None:
        header = b"a" * 40
        for frame in [
            b"",
            b"bad\n",
            header + b" blob -1\n",
            header + b" blob 01\n",
            header + b" blob 2\nA",
            header + b" blob 2\nAB!",
            header + b" blob 2\nAB",
            header + b" mystery 0\n\n",
        ]:
            with self.subTest(frame=frame):
                script = f"import sys; sys.stdin.buffer.readline(); sys.stdout.buffer.write({frame!r}); sys.stdout.buffer.flush()"

                def read():
                    with GitReader() as reader:
                        with self.assertRaises(ValueError):
                            reader.read(Path.cwd(), "a" * 40, "source")
                        with self.assertRaisesRegex(ValueError, "closed"):
                            reader.read(Path.cwd(), "a" * 40, "source")

                self.run_peer(script, read)

    def test_nonzero_exit_after_a_complete_reply_is_still_a_failure(self) -> None:
        frame = b"a" * 40 + b" blob 2\nok\n"
        script = f"import sys; sys.stdin.buffer.readline(); sys.stdout.buffer.write({frame!r}); sys.stdout.buffer.flush(); sys.exit(7)"

        def read():
            with self.assertRaisesRegex(ValueError, "status 7"):
                with GitReader() as reader:
                    self.assertEqual(reader.read(Path.cwd(), "a" * 40, "source"), "ok")

        self.run_peer(script, read)

    def test_a_broken_input_pipe_is_reaped(self) -> None:
        popen = subprocess.Popen
        children = []

        def start(*args, **kwargs):
            child = popen(
                [
                    sys.executable,
                    "-c",
                    "import os,sys; os.close(0); print('ready', flush=True)",
                ],
                **kwargs,
            )
            self.assertEqual(child.stdout.readline(), b"ready\n")
            children.append(child)
            return child

        with patch("traceability._git.subprocess.Popen", side_effect=start):
            with (
                self.assertRaisesRegex(ValueError, "source unavailable"),
                GitReader() as reader,
            ):
                reader.read(Path.cwd(), "a" * 40, "source")
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stdin.closed)
        self.assertTrue(children[0].stdout.closed)

    def test_abnormal_exit_does_not_mask_the_callers_exception(self) -> None:
        frame = b"a" * 40 + b" blob 2\nok\n"
        script = f"import sys; sys.stdin.buffer.readline(); sys.stdout.buffer.write({frame!r}); sys.stdout.buffer.flush(); sys.exit(7)"

        def read():
            with self.assertRaisesRegex(RuntimeError, "original"):
                with GitReader() as reader:
                    reader.read(Path.cwd(), "a" * 40, "source")
                    raise RuntimeError("original")

        self.run_peer(script, read)

    def test_child_that_ignores_eof_is_killed_and_reaped(self) -> None:
        frame = b"a" * 40 + b" blob 2\nok\n"
        script = f"import sys,time; sys.stdin.buffer.readline(); sys.stdout.buffer.write({frame!r}); sys.stdout.buffer.flush(); sys.stdin.buffer.read(); time.sleep(60)"

        def read():
            with self.assertRaisesRegex(ValueError, "timed out"):
                with GitReader() as reader:
                    reader.read(Path.cwd(), "a" * 40, "source")

        self.run_peer(script, read)


if __name__ == "__main__":
    unittest.main()
