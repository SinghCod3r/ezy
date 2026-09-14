"""Filesystem operations backing the `create`, `write`, `append`, `read`,
`delete` statements/expressions and the `list files in` and `exists` forms.

All paths accept either a plain string or an EzyPath. Errors are raised as
EzyRuntimeError with error_type "FileError" so Ezy scripts can catch them.
"""

from __future__ import annotations

import os
import shutil
from typing import List, Union

from ..errors import EzyRuntimeError
from ..values import EzyPath

PathLike = Union[str, EzyPath]


def _s(path: PathLike) -> str:
    return path.raw if isinstance(path, EzyPath) else str(path)


def create_file(path: PathLike) -> None:
    p = _s(path)
    directory = os.path.dirname(p)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    try:
        with open(p, "a", encoding="utf-8"):
            pass
    except OSError as exc:
        raise EzyRuntimeError(f"could not create file {p!r}: {exc.strerror}", "FileError") from exc


def create_folder(path: PathLike) -> None:
    p = _s(path)
    try:
        os.makedirs(p, exist_ok=True)
    except OSError as exc:
        raise EzyRuntimeError(f"could not create folder {p!r}: {exc.strerror}", "FileError") from exc


def write_file(path: PathLike, content: str) -> None:
    p = _s(path)
    directory = os.path.dirname(p)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        raise EzyRuntimeError(f"could not write to {p!r}: {exc.strerror}", "FileError") from exc


def append_file(path: PathLike, content: str) -> None:
    p = _s(path)
    directory = os.path.dirname(p)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        raise EzyRuntimeError(f"could not append to {p!r}: {exc.strerror}", "FileError") from exc


def read_file(path: PathLike) -> str:
    p = _s(path)
    if not os.path.exists(p):
        raise EzyRuntimeError(f"file not found: {p!r}", "FileError")
    if os.path.isdir(p):
        raise EzyRuntimeError(f"{p!r} is a folder, not a file", "FileError")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as exc:
        raise EzyRuntimeError(
            f"{p!r} is not valid UTF-8 text (binary files are not yet supported by 'read')",
            "FileError",
        ) from exc
    except OSError as exc:
        raise EzyRuntimeError(f"could not read {p!r}: {exc.strerror}", "FileError") from exc


def delete_file(path: PathLike) -> None:
    p = _s(path)
    if not os.path.exists(p):
        raise EzyRuntimeError(f"file not found: {p!r}", "FileError")
    try:
        os.remove(p)
    except OSError as exc:
        raise EzyRuntimeError(f"could not delete {p!r}: {exc.strerror}", "FileError") from exc


def delete_folder(path: PathLike) -> None:
    p = _s(path)
    if not os.path.exists(p):
        raise EzyRuntimeError(f"folder not found: {p!r}", "FileError")
    try:
        shutil.rmtree(p)
    except OSError as exc:
        raise EzyRuntimeError(f"could not delete folder {p!r}: {exc.strerror}", "FileError") from exc


def list_files(path: PathLike) -> List[EzyPath]:
    p = _s(path)
    if not os.path.isdir(p):
        raise EzyRuntimeError(f"not a folder: {p!r}", "FileError")
    try:
        names = sorted(os.listdir(p))
    except OSError as exc:
        raise EzyRuntimeError(f"could not list {p!r}: {exc.strerror}", "FileError") from exc
    return [EzyPath(os.path.join(p, name)) for name in names]


def path_exists(path) -> bool:
    if isinstance(path, EzyPath):
        return path.exists
    return os.path.exists(str(path))


def file_exists(path: PathLike) -> bool:
    return os.path.isfile(_s(path))


def folder_exists(path: PathLike) -> bool:
    return os.path.isdir(_s(path))
