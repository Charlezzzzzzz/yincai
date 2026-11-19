"""Resolve packaged evidence relative to this checkout and check its bytes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "teaching_case"


def case_index(root: Path) -> dict:
    return json.loads((root / "index.json").read_bytes())


def read_cache_bytes(root: Path, relative_path: str) -> bytes:
    metadata = case_index(root)["records"][relative_path]
    path = (root / relative_path).resolve()
    if not path.is_relative_to((root / "cache").resolve()):
        raise ValueError("教学缓存路径不在案例目录内")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata["public_sha256"]:
        raise ValueError("公开缓存与来源清单中的文件哈希不符")
    return content


def read_cache(root: Path, relative_path: str) -> dict:
    return json.loads(read_cache_bytes(root, relative_path))
