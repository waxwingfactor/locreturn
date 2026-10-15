"""Bounded JSON I/O and exclusive bundle output, with no catalog mutation."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .core import MAX_FILE, Invalid, require


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON contains a duplicate object key")
        result[key] = value
    return result


def invalid_constant(value: str) -> None:
    raise Invalid(f"non-finite JSON value is unsupported: {value}")


def read_json(path: Path) -> dict:
    # Nonblocking open lets us reject FIFOs/devices without waiting for writers.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode), "input must be a regular JSON file")
        require(info.st_size <= MAX_FILE, f"input exceeds {MAX_FILE} bytes")
        raw = stream.read(MAX_FILE + 1)
    require(len(raw) <= MAX_FILE, f"input exceeds {MAX_FILE} bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant)
    except Invalid:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise Invalid(f"invalid UTF-8 JSON: {exc.__class__.__name__}") from exc


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False) + "\n").encode("utf-8")


def write_bundle(folder: Path, files: dict[str, dict | str]) -> None:
    """Pre-serialize every file, then claim a new directory exclusively.

    Single-writer local filesystems are supported. A directory may be visible
    while being populated. On ordinary failures remove only files we created.
    Never overwrite an existing path, follow an output symlink, or edit inputs.
    """
    encoded = {name: value.encode("utf-8") if isinstance(value, str) else json_bytes(value)
               for name, value in files.items()}
    for value in encoded.values():
        require(len(value) <= MAX_FILE, f"generated file exceeds {MAX_FILE} bytes; use a smaller catalog")
    created = []
    folder.mkdir()  # exclusive; existing directories, files and symlinks fail
    try:
        for name, value in encoded.items():
            with (folder / name).open("xb") as stream:
                created.append(folder / name)
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
    except BaseException:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        try:
            folder.rmdir()
        except OSError:
            pass
        raise


def review_text(p: dict) -> str:
    lines = ["locreturn review", f"Plan: {p['plan_id']}",
             f"Locale: {p['source_locale']} -> {p['target_locale']}",
             f"Conflicts requiring decisions: {p['conflicts']}",
             "Counts: " + json.dumps(p["counts"], sort_keys=True),
             "Review source, context, and target changes below.",
             "Success does not certify translation quality, runtime syntax, or source currency.", ""]
    # JSON escaping prevents terminal control codes and misleading multiline rows.
    for row in p["rows"]:
        lines.append(json.dumps(row, ensure_ascii=True, sort_keys=True))
    return "\n".join(lines) + "\n"
