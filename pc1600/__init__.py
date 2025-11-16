from __future__ import annotations

import json
from pathlib import Path
from pc1600.data import data_factory
from pc1600.patch import SysexPatch, Section, flatten_section
from pc1600.utils import short_to_bytes, pack_sysex


def sysex_file_to_sysex_patch(sysex_file: str) -> SysexPatch:
    with Path(sysex_file).open("rb") as f:
        return SysexPatch(f.read())


def json_file_to_sysex_patch(json_file: str) -> SysexPatch:
    with Path(json_file).open("r", encoding="utf-8") as f:
        data = json.load(f)
    return sections_to_sysex_patch(**data)


def raw_to_sysex(name: str, global_channel: int, raw: bytes) -> bytearray:
    padded_name = bytes(name.encode()).ljust(16)
    raw_length = short_to_bytes(len(raw))
    unpacked = data_factory(padded_name, raw_length, raw)
    return pack_sysex(unpacked, global_channel=global_channel)


def sections_to_sysex_patch(
    buttons: list[dict[str, int | str]],
    cvs: list[dict[str, int | str]],
    data_wheel: list[dict[str, int | str]],
    faders: list[dict[str, int | str]],
    file_version: str,
    global_channel: int,
    name: str,
    setup: list[dict[str, int | str]],
) -> SysexPatch:
    if file_version != "1.0.0":
        msg = f"Unsupported file version: {file_version}"
        raise ValueError(msg)

    raw = flatten_section(Section.FADERS, faders)
    raw += flatten_section(Section.CVS, cvs)
    raw += flatten_section(Section.BUTTONS, buttons)
    raw += flatten_section(Section.DATA_WHEEL, data_wheel)
    raw += flatten_section(Section.SETUP, setup)
    return SysexPatch(raw_to_sysex(name, global_channel, raw))
