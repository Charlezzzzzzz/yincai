"""Cross-process lock used only by the optional local Ollama provider."""
from contextlib import contextmanager
import os
from pathlib import Path
import sys


@contextmanager
def ollama_request_lock():
    lock_path = Path(os.environ.get("OLLAMA_REQUEST_LOCK", Path.home() / ".yincai" / "ollama.lock")).expanduser()
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with lock_path.open("a+b") as file:
        if sys.platform == "win32":
            import msvcrt
            if file.tell() == 0:
                file.write(b"0")
                file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)
