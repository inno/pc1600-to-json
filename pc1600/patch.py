import enum
import json
from dataclasses import dataclass, field
from collections import defaultdict
from pc1600.record import (
    Record,
    button_types,
    data_wheel_types,
    fader_types,
    setup_types,
)
from pc1600.data import Data
from pc1600.utils import (
    int_to_nibbles,
    pack_sysex,
    short_to_bytes,
    unpack_sysex,
)


__version__ = "1.0.0"


class Section(enum.StrEnum):
    BUTTON = enum.auto()
    CV = enum.auto()
    DATA_WHEEL = "data wheel"
    FADER = enum.auto()
    SETUP = enum.auto()


@dataclass
class Patch:
    raw_data: bytes
    data: None | Data = None
    _records: list[Record] = field(default_factory=list)

    def __post_init__(self):
        self.data = unpack_sysex(self.raw_data)
        # Exclude name and size fields
        if len(self.data) - (16 + 2) != self.data_size:
            print("ERROR: Data length != size field!")
            exit()
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
        current_section = Section.FADER
        record_id = 1
        while True:
            if record_id == 17:
                current_section = Section.CV
            elif record_id == 19:
                current_section = Section.BUTTON
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

    def rebundle(self) -> bytes:
        raw = b"".join([r.rebundle() for r in self.records()])
        name = bytes(self.name.encode()).ljust(16)
        data_length = short_to_bytes(len(raw))
        return name + data_length + raw

    def to_dict(self) -> dict[str, list[dict[str, ...]]]:
        result = defaultdict(defaultdict(list).copy)
        for record in self.records():
            if record.section not in result:
                result[record.section] = []
            result[record.section].append(record.to_dict())
        result["name"] = self.name.rstrip()
        result["global_channel"] = self.global_channel
        result["file version"] = self.version
        return dict(result)

    def to_json(self) -> str:
        class BytesToHexEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, bytearray):
                    return o.hex()
                return super().default(o)

        return json.dumps(self.to_dict(), indent=4, cls=BytesToHexEncoder)

    def to_syx(self) -> bytes:
        return pack_sysex(self.rebundle(), self.global_channel)

    def record_factory(
        self,
        offset: int,
        section: Section,
    ) -> Record:
        section_str = str(section)
        data = self.data.bytearray(offset, self.data[offset - 1])
        record_type = int_to_nibbles(data[0])[1]
        if section in (Section.FADER, Section.CV):
            return fader_types[record_type](data=data, section=section_str)
        elif section == Section.BUTTON:
            return button_types[record_type](data=data, section=section_str)
        elif section == Section.DATA_WHEEL:
            return data_wheel_types[record_type](data=data, section=section_str)
        elif section == Section.SETUP:
            return setup_types[record_type](data=data, section=section_str)
