"""Rebuild build/cache/types.py from the dataclasses in src/models.py."""

import sys
import zlib
from dataclasses import fields, is_dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import src.models as models  # noqa: E402


def _model_classes():
    out = []
    for name in dir(models):
        obj = getattr(models, name)
        if isinstance(obj, type) and is_dataclass(obj) and obj.__module__ == models.__name__:
            out.append(obj)
    return sorted(out, key=lambda c: c.__name__)


def _emit(cls_list) -> str:
    lines = ["import zlib", "", ""]

    for cls in cls_list:
        fs = [f.name for f in fields(cls)]
        rec = f"{cls.__name__}Record"
        lines.append(f"class {rec}:")
        lines.append(f"    __slots__ = ({', '.join(repr(f) for f in fs)},)")
        lines.append("")
        lines.append(f"    def __init__(self, {', '.join(fs)}):")
        for f in fs:
            lines.append(f"        self.{f} = {f}")
        lines.append("")
        lines.append("")

    for cls in cls_list:
        fs = [f.name for f in fields(cls)]
        v = zlib.crc32(",".join(fs).encode())
        lines.append(f"def _pack_{cls.__name__.lower()}(rec):")
        kv = ", ".join(f"{f!r}: rec.{f}" for f in fs)
        lines.append(f"    return {{'kind': {cls.__name__!r}, 'v': {v}, {kv}}}")
        lines.append("")
        lines.append("")

    fields_map = ", ".join(
        f"{c.__name__!r}: ({', '.join(repr(f.name) for f in fields(c))},)" for c in cls_list
    )
    schema_map = ", ".join(
        f"{c.__name__!r}: {zlib.crc32(','.join(f.name for f in fields(c)).encode())}"
        for c in cls_list
    )
    records_map = ", ".join(f"{c.__name__!r}: {c.__name__}Record" for c in cls_list)
    packers_map = ", ".join(f"{c.__name__!r}: _pack_{c.__name__.lower()}" for c in cls_list)

    lines += [
        f"_FIELDS = {{{fields_map}}}",
        f"_SCHEMA_V = {{{schema_map}}}",
        f"_RECORDS = {{{records_map}}}",
        f"_PACKERS = {{{packers_map}}}",
        "",
        "for _k, _fs in _FIELDS.items():",
        "    if zlib.crc32(','.join(_fs).encode()) != _SCHEMA_V[_k]:",
        "        raise RuntimeError(",
        "            f'record table corrupt for {_k!r} '",
        "            f'(checksum {zlib.crc32(\",\".join(_fs).encode())} != {_SCHEMA_V[_k]})'",
        "        )",
        "",
        "",
        "def to_record(obj):",
        "    kind = type(obj).__name__",
        "    if kind not in _FIELDS:",
        "        raise TypeError(f'no record type for {kind!r}')",
        "    return _RECORDS[kind](*[getattr(obj, f) for f in _FIELDS[kind]])",
        "",
        "",
        "def pack(rec):",
        "    kind = type(rec).__name__[:-len('Record')]",
        "    return _PACKERS[kind](rec)",
        "",
        "",
        "def unpack(payload):",
        "    kind = payload['kind']",
        "    if payload.get('v') != _SCHEMA_V[kind]:",
        "        raise ValueError(",
        "            f'record schema mismatch for {kind!r}: '",
        "            f'payload v={payload.get(\"v\")}, expected {_SCHEMA_V[kind]}'",
        "        )",
        "    extra = set(payload) - {'kind', 'v', *_FIELDS[kind]}",
        "    if extra:",
        "        raise ValueError(f'unexpected keys in {kind!r} payload: {sorted(extra)}')",
        "    return _RECORDS[kind](*[payload[f] for f in _FIELDS[kind]])",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    out_dir = ROOT / "build" / "cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "build" / "__init__.py").touch()
    (out_dir / "__init__.py").touch()
    (out_dir / "types.py").write_text(_emit(_model_classes()), encoding="utf-8")
    print(f"wrote {out_dir / 'types.py'}")


if __name__ == "__main__":
    main()
