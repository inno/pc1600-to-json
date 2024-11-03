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
from pc1600.utils import int_to_nibbles, short_to_bytes, unpack_sysex


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
    _active_section: Section = Section.FADER
    _record_id: int = 0
    _record_offset: int = 19
    _records: dict[str, ...] = field(default_factory=dict)

    def __post_init__(self):
        self.data = unpack_sysex(self.raw_data)
        # Exclude name and size fields
        if len(self.data) - (16 + 2) != self.data_size:
            print("ERROR: Data length != size field!")
            exit()

    @property
    def name(self) -> str:
        return self.data.string(0, 16)

    @property
    def channel(self) -> int:
        return self.raw_data[5]

    @property
    def data_size(self) -> int:
        return self.data.short(16)

    @property
    def version(self) -> str:
        return __version__

    def records(self) -> dict[Section, list[Record]]:
        if self._records:
            return self._records
        self._records = {
            Section.FADER: [],
            Section.CV: [],
            Section.BUTTON: [],
            Section.DATA_WHEEL: [],
            Section.SETUP: [],
        }
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
            self._records[current_section].append(record)
            record_offset += record.length()
            if record_offset == len(self.data):
                break
            record_id += 1
        return self._records

    def rebundle(self) -> bytes:
        flat_records = [r for rs in self.records().values() for r in rs]
        return (
            bytes(self.name.encode())
            + short_to_bytes(self.data_size)
            + b"".join([r.rebundle() for r in flat_records])
        )

    def to_dict(self) -> dict[str, list[dict[str, ...]]]:
        result = defaultdict(list)
        for section, records in self.records().items():
            for record in records:
                result[str(section)].append(record.to_dict())
        result["name"] = self.name.rstrip()
        result["channel"] = self.channel
        result["file version"] = self.version
        return dict(result)

    def to_json(self) -> str:
        class BytesToHexEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, bytearray):
                    return o.hex()
                return super().default(o)

        return json.dumps(self.to_dict(), indent=4, cls=BytesToHexEncoder)

    def record_factory(
        self,
        offset: int,
        section: Section,
    ) -> Record:
        data = self.data.bytearray(offset, self.data[offset - 1])
        record_type = int_to_nibbles(data[0])[1]
        if section in (Section.FADER, Section.CV):
            return fader_types[record_type](data=data, section=section)
        elif section == Section.BUTTON:
            return button_types[record_type](data=data, section=section)
        elif section == Section.DATA_WHEEL:
            return data_wheel_types[record_type](data=data, section=section)
        elif section == Section.SETUP:
            return setup_types[record_type](data=data, section=section)
