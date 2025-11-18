from __future__ import annotations

import enum
import json
from pc1600.data import Data
from pc1600.record import (
    Record,
    button_types,
    data_wheel_types,
    fader_types,
    setup_types,
    name_to_button_id,
    name_to_data_wheel_id,
    name_to_fader_id,
    name_to_setup_id,
)
from pc1600.utils import (
    int_to_nibbles,
    pack_sysex,
    short_to_bytes,
    unpack_sysex,
)
from typing import Any, TypedDict

__version__ = "1.0.0"


class Section(enum.StrEnum):
    BUTTONS = enum.auto()
    CVS = enum.auto()
    DATA_WHEEL = enum.auto()
    FADERS = enum.auto()
    SETUP = enum.auto()


class JSONFileStructure(TypedDict):
    name: str
    global_channel: int
    file_version: str
    buttons: list[dict[str, Any]]
    cvs: list[dict[str, Any]]
    data_wheel: list[dict[str, Any]]
    faders: list[dict[str, Any]]
    setup: list[dict[str, Any]]


section_lookup = {
    Section.FADERS: name_to_fader_id,
    Section.CVS: name_to_fader_id,
    Section.BUTTONS: name_to_button_id,
    Section.DATA_WHEEL: name_to_data_wheel_id,
    Section.SETUP: name_to_setup_id,
}


def extract_sections(records: list[Record]) -> dict[str, list[Record]]:
    return {
        section: [r for r in records if r.section == section]
        for section in section_lookup
    }


def flatten_section(
    section: Section,
    items: list[dict[str, int | str]],
) -> bytes:
    raw = b""
    for item in items:
        section_data = section_lookup[section][str(item["type"])]
        record = section_data.pack(section, **item)
        raw += record.flatten()
    return raw


class SysexPatch:
    raw_data: bytes
    data: Data
    _records: list[Record]

    def __init__(self, raw_data: bytes) -> None:
        self.raw_data = raw_data
        self.data = Data(unpack_sysex(self.raw_data))
        # Exclude name and size fields
        if len(self.data) - (16 + 2) != self.data_size:
            msg = "Data length != size field!"
            raise ValueError(msg)
        self.parse_records()

    @property
    def name(self) -> str:
        return self.data.string(0, 16)

    @property
    def global_channel(self) -> int:
        return self.raw_data[5]

    @property
    def data_size(self) -> int:
        return self.data.short(16)

    @property
    def version(self) -> str:
        return __version__

    def records(self) -> list[Record]:
        if not self._records:
            self.parse_records()
        return self._records

    def parse_records(self) -> None:
        self._records = []
        record_offset = 18
        current_section = Section.FADERS
        record_id = 1
        while True:
            if record_id == 17:
                current_section = Section.CVS
            elif record_id == 19:
                current_section = Section.BUTTONS
            elif record_id == 35:
                current_section = Section.DATA_WHEEL
            elif record_id == 36:
                current_section = Section.SETUP
            record_offset += 1
            record = self.record_factory(
                offset=record_offset,
                section=current_section,
            )
            self._records.append(record)
            record_offset += record.length()
            if record_offset == len(self.data):
                break
            record_id += 1

    def flatten(self) -> bytes:
        raw = b"".join([r.flatten() for r in self.records()])
        name = bytes(self.name.encode()).ljust(16)
        data_length = short_to_bytes(len(raw))
        return name + data_length + raw

    def to_dict(self) -> JSONFileStructure:
        records = self.records()
        sections = extract_sections(records)
        return JSONFileStructure(
            name=self.name.rstrip(),
            global_channel=self.global_channel,
            file_version=self.version,
            buttons=[r.to_dict() for r in sections[Section.BUTTONS]],
            cvs=[r.to_dict() for r in sections[Section.CVS]],
            data_wheel=[r.to_dict() for r in sections[Section.DATA_WHEEL]],
            faders=[r.to_dict() for r in sections[Section.FADERS]],
            setup=[r.to_dict() for r in sections[Section.SETUP]],
        )

    def to_json(self) -> str:
        class BytesToHexEncoder(json.JSONEncoder):
            def default(self, o: Any) -> Any:  # noqa: ANN401
                if isinstance(o, bytearray):
                    return o.hex()
                return super().default(o)

        return json.dumps(self.to_dict(), indent=4, cls=BytesToHexEncoder)

    def to_raw_sysex(self) -> bytes:
        return pack_sysex(self.flatten(), self.global_channel)

    def record_factory(
        self,
        offset: int,
        section: Section,
    ) -> Record:
        data = self.data.bytearray(offset, self.data[offset - 1])
        record_type = int_to_nibbles(data[0])[1]
        if section in (Section.FADERS, Section.CVS):
            return fader_types[record_type](section, data)
        if section == Section.BUTTONS:
            return button_types[record_type](section, data)
        if section == Section.DATA_WHEEL:
            return data_wheel_types[record_type](section, data)
        if section == Section.SETUP:
            return setup_types[record_type](section, data)
        raise ValueError("Unknown section: " + section)
