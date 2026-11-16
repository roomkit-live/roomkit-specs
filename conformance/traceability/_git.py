"""Scoped, sequential Git blob reads without a process per source reference."""

from __future__ import annotations

import io
import os
import re
import subprocess
from pathlib import Path
from types import TracebackType

from .references import git_text, validate_git_reference

_HEADER = re.compile(
    rb"(?:[0-9a-f]{40}|[0-9a-f]{64}) (blob|tree|commit|tag) (0|[1-9][0-9]*)\n"
)


class _Batch:
    def __init__(self, repo: Path) -> None:
        self.process = subprocess.Popen(
            ["git", "-C", str(repo), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.closed = False
        assert self.process.stdin is not None and self.process.stdout is not None

    def read(self, address: str) -> tuple[bytes, bytes] | None:
        if self.closed:
            raise ValueError("Git batch reader is closed")
        try:
            return self._exchange(os.fsencode(address))
        except BaseException as error:
            # A partial request or reply loses framing. Never reuse that stream,
            # including after a caller interrupts a read.
            try:
                self.close(check=False)
            except BaseException:
                pass  # Preserve the failed or interrupted read, not cleanup errors.
            if isinstance(error, BrokenPipeError):
                raise ValueError(f"source unavailable: {address}") from error
            raise

    def _exchange(self, address: bytes) -> tuple[bytes, bytes] | None:
        stdin, stdout = self.process.stdin, self.process.stdout
        assert stdin is not None and stdout is not None
        stdin.write(address + b"\n")
        stdin.flush()
        header = stdout.readline()
        if not header:
            raise ValueError(f"source unavailable: {os.fsdecode(address)}")
        if header == address + b" missing\n":
            return None
        match = _HEADER.fullmatch(header)
        if match is None:
            raise ValueError("invalid Git batch response header")
        size = int(match[2])
        body = stdout.read(size)
        if len(body) != size or stdout.read(1) != b"\n":
            raise ValueError("truncated Git batch response")
        return match[1], body

    def close(self, *, check: bool = True) -> None:
        if self.closed:
            return
        self.closed = True
        process = self.process
        assert process.stdin is not None and process.stdout is not None
        failure = None
        try:
            process.stdin.close()
            code = process.wait(timeout=5)
            if code:
                failure = ValueError(f"Git batch reader exited with status {code}")
        except (OSError, subprocess.TimeoutExpired) as error:
            failure = error
        finally:
            # Only this reader's own child is stopped. Both normal completion and
            # a broken pipe must reap it, without waiting indefinitely on exit.
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
        if check and failure is not None:
            raise ValueError(f"cannot close Git batch reader: {failure}") from failure


class GitReader:
    """One process per explicit repository, owned by one validation call.

    Every logical read still runs: no blob or validation result is cached. A
    worktree is its own repository key even if its Git common directory is shared.
    """

    def __init__(self) -> None:
        self._batches: dict[Path, _Batch] = {}
        self._closed = False

    def __enter__(self) -> GitReader:
        if self._closed:
            raise ValueError("Git reader is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._closed = True
        failure = None
        for batch in self._batches.values():
            try:
                batch.close(check=exc_type is None)
            except BaseException as error:
                failure = failure or error
        if failure is not None and exc_type is None:
            raise failure

    def read(self, repo: Path, commit: str, path: str) -> str:
        if self._closed:
            raise ValueError("Git reader is closed")
        validate_git_reference(commit, path)
        # These are legal to the old reader (except NUL, rejected by subprocess),
        # but cannot be injected into cat-file's line-framed input.
        if any(character in path for character in "\n\r\0"):
            return git_text(repo, commit, path)
        key = repo.resolve()
        if key not in self._batches:
            self._batches[key] = _Batch(key)
        result = self._batches[key].read(f"{commit}:{path}")
        if result is None:
            raise ValueError(f"source unavailable: {commit}:{path}")
        kind, body = result
        if kind != b"blob":
            # git show renders trees differently; the consumed batch response
            # remains aligned for the next ordinary file read.
            return git_text(repo, commit, path)
        # Match subprocess(text=True): locale/UTF-8 mode, universal newlines,
        # strict decoding, and no stripping of whitespace or final newlines.
        with io.TextIOWrapper(io.BytesIO(body)) as text:
            return text.read()
