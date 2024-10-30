import enum
import json
import simplecli
import struct
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


__version__ = "1.0.0"


class Data(bytes):
    def short(self, offset: int) -> int:
        return struct.unpack(">h", self[offset: offset + 2])[0]

    def bytearray(self, offset: int, length: int) -> bytes:
        return Data(self[offset:offset + length])

    def string(self, offset: int, length: int) -> str:
        if length == 0:
            return ""
        result = ""
        for c in self.bytearray(offset, length):
            if c < 32 or 126 < c:
                print(
                    "ERROR: "
                    f"Invalid character detected! [{hex(c)}] "
                    "Either we have processed a record wrong "
                    "or the file is corrupt. "
                    f"Attempt to stringify {self.bytearray(offset, length)}"
                )
                exit()
            result += chr(c)
        return result

    def debug(self, offset: int = 0, length: None | int = None):
        print("### DEBUG ###")
        if length is None:
            length = len(self)
        for i in range(length):
            char = "" if self[i] < 32 or 126 < self[i] else chr(self[i])
            print(f"{i}:\t{self[i]}\t{hex(self[i])}\t{char}")


@dataclass
class Input:
    section: str
    data: Data

    def __str__(self):
        properties = []
        for prop in dir(self):
            if prop.startswith("_"):
                continue
            if prop == "data":
                continue
            if prop == "type_and_name_length":
                continue
            if callable(getattr(self, prop)):
                continue
            value = getattr(self, prop)
            if prop == "name" and not value:
                continue
            properties.append(f"{prop}={value}")
        return f"{type(self).__name__}({', '.join(properties)})"

    def to_dict(self):
        result = {}
        for prop in dir(self):
            if prop in self.fields():
                value = getattr(self, prop)
                if prop in ("name", "channels") and not value:
                    continue
                if prop == "scene" and value is None:
                    continue
                result[prop] = value
        result["type"] = type(self).__name__
        return result

    def fields(self) -> list[str]:
        return ["type", "name"] + [
            p
            for p in vars(self.__class__)
            if not p.startswith("_")
            and isinstance(getattr(self.__class__, p), property)
        ]

    @property
    def name(self) -> str:
        return self.data.string(self._name_offset, self._name_length)

    @property
    def _name_length(self) -> int:
        return self.data[0] >> 4

    @property
    def _name_offset(self) -> int:
        return 6 if self._name_length else 0

    def length(self):
        return len(self.data)

    def rebundle(self):
        return bytes([self.length()]) + self.data[:self.length()]

    @property
    def _type(self):
        raise Exception("'type' must be defined in this class!")

    @property
    def type_and_name_length(self):
        return nibbles_to_int(self._type, len(self.name))


@dataclass
class Disabled(Input):
    _type = 0
    _name_offset = 0
    _raw_fields = [
        "type_and_name_length",
        "name",
    ]


@dataclass
class CC(Input):
    _type = 1
    _raw_fields = [
        "type_and_name_length",
        "min",
        "max",
        "channel",
        "cc",
        "mode",
        "name",
    ]

    @property
    def min(self):
        return self.data[1]

    @property
    def max(self):
        return self.data[2]

    # gc = global channel (0xFE?)
    # -gc = channelized previous byte  (0xFE)
    # dv = device number   (0xFD)
    # rv = remote velocity (0xFF)

    @property
    def channel(self):
        return self.data[3]

    @property
    def cc(self):
        return self.data[4]

    @property
    def mode(self):
        return self.data[5]


@dataclass
class Master(Input):
    _type = 2
    _name_length = 0
    _name_offset = 0
    _raw_fields = [
        "type_and_name_length",
        "faders",
        "name",
    ]

    @property
    def faders(self):
        bitmap = [i+1 for i in range(8) if 0x1 & self.data[1] >> i]
        bitmap += [i+9 for i in range(8) if 0x1 & self.data[2] >> i]
        return bitmap


@dataclass
class String(Input):
    _type = 3

    @property
    def _name_offset(self):
        return 7 + self._string_length

    @property
    def param_format(self):
        return param_format_lookup[self.data[1]]

    @property
    def _string_length(self) -> int:
        return self.data[6]

    @property
    def sysex(self) -> int:
        return self.data[7:self._string_length + 7]

    @property
    def min(self) -> int:
        return self.data.short(2)

    @property
    def max(self) -> int:
        return self.data.short(4)


@dataclass
class Mute(Input):
    _type = 1
    _name_offset = 1
    _raw_fields = [
        "type_and_name_length",
        "name",
    ]


@dataclass
class Solo(Input):
    _type = 2
    _name_offset = 1
    _raw_fields = [
        "type_and_name_length",
        "name",
    ]


@dataclass
class ProgramChange(Input):
    _type = 3
    _name_offset = 3
    _raw_fields = [
        "type_and_name_length",
        "channel",
        "program",
        "name",
    ]

    @property
    def channel(self):
        return self.data[1]

    @property
    def program(self):
        return self.data[2]


@dataclass
class NoteOnOff(Input):
    _type = 4
    _name_offset = 4
    _raw_fields = [
        "type_and_name_length",
        "channel",
        "note",
        "velocity",
        "name",
    ]

    @property
    def channel(self):
        return self.data[1]

    @property
    def note(self):
        return self.data[2]

    @property
    def velocity(self):
        return self.data[3]


@dataclass
class ButtonString(Input):
    _type = 5
    _raw_fields = [
        "type_and_name_length",
        "_string_length",
        "value",
        "name",
    ]

    @property
    def _name_offset(self):
        return 2 + self._string_length

    @property
    def _string_length(self) -> int:
        return self.data[1]

    @property
    def sysex(self) -> int:
        return self.data[2:self._string_length + 2]


@dataclass
class StringPressRelease(Input):
    _type = 6

    @property
    def _name_offset(self) -> int:
        return self._value2_offset + self._value2_length

    @property
    def press(self) -> bytes:
        return self.data.bytearray(2, self._value1_length)

    @property
    def _value1_length(self) -> int:
        return self.data[1]

    @property
    def release(self) -> bytes:
        return self.data.bytearray(self._value2_offset, self._value2_length)

    @property
    def _value2_length(self) -> int:
        return self.data[self._value2_offset - 1]

    @property
    def _value2_offset(self) -> int:
        return self._value1_length + 3


@dataclass
class StringToggle(Input):
    _type = 7

    @property
    def _name_offset(self) -> int:
        return self._value2_offset + self._value2_length

    @property
    def sysex1(self) -> bytes:
        return self.data.bytearray(2, self._value1_length)

    @property
    def _value1_length(self) -> int:
        return self.data[1]

    @property
    def sysex2(self) -> bytes:
        return self.data.bytearray(self._value2_offset, self._value2_length)

    @property
    def _value2_length(self) -> int:
        return self.data[self._value2_offset - 1]

    @property
    def _value2_offset(self) -> int:
        return self._value1_length + 3


@dataclass
class SendFader(Input):
    _type = 8
    _name_offset = 1
    _raw_fields = [
        "type_and_name_length",
        "name",
    ]


@dataclass
class SendScene(Input):
    _type = 9
    _name_offset = 1
    _raw_fields = [
        "type_and_name_length",
        "name",
        "value",
    ]

    @property
    def value(self):
        return self.data[1]


@dataclass
class DataWheel(Input):
    _type = 1
    _name_offset = 0

    @property
    def mapped_to(self):
        wheel_lookup = {i: f"Fader {i+1}" for i in range(16)}
        wheel_lookup[16] = "CV 1"
        wheel_lookup[17] = "CV 2"
        wheel_lookup[18] = "Last fader"
        return wheel_lookup[self.data[1]]


@dataclass
class Setup(Input):
    _type = 1
    _name_offset = 0

    @property
    def _midi_channels(self):
        bitmap = [i+1 for i in range(8) if 0x1 & self.data[1] >> i]
        bitmap += [i+9 for i in range(8) if 0x1 & self.data[2] >> i]
        return bitmap

    @property
    def channels(self):
        def seven_bit(value) -> str | int:
            return value - 0x80 if value & 0x80 else "Off"

        def folded(value) -> str | int:
            return value - 0x80 if value & 0x80 else f"{value + 1}m"

        channels = {}
        offset = 3
        for channel in self._midi_channels:
            print(offset, self.data[offset])
            channels[channel] = {
                "bank": folded(self.data[offset]),
                "program": seven_bit(self.data[offset + 1]),
                "volume": seven_bit(self.data[offset + 2]),
            }
            offset += 3
        return channels

    @property
    def _scene_offset(self) -> int:
        return 3 + len(self._midi_channels) * 3

    @property
    def _has_sysex(self) -> bool:
        return bool(self._sysex_length)

    @property
    def _sysex_offset(self) -> int:
        return self._scene_offset + (self._has_scene * 2)

    @property
    def _has_scene(self) -> bool:
        return self.data[self._scene_offset] == 0xfe

    @property
    def scene(self) -> int:
        if not self._has_scene:
            return None
        return self.data[self._scene_offset + 1]

    @property
    def _sysex_length(self) -> int:
        return self.data[self._sysex_offset]

    @property
    def sysex(self) -> Data:
        if not self._has_sysex:
            return None
        return self.data.bytearray(self._sysex_offset + 1, self._sysex_length)


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
        self.data = unpack(self.raw_data)
        # Exclude name and size fields
        if len(self.data) - (16 + 2) != self.data_size:
            print("ERROR: Data length != size field!")
            exit()

    @property
    def name(self) -> str:
        return self.data.string(0, 16)

    @property
    def data_size(self) -> int:
        return self.data.short(16)

    @property
    def version(self) -> str:
        return __version__

    def records(self) -> dict[Section, list[Input]]:
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
            record_length = self.data[record_offset]
            record_offset += 1
            record = record_factory(
                data=self.data.bytearray(record_offset, record_length),
                section=current_section,
            )
            self._records[current_section].append(record)
            record_offset += record.length()
            if record_offset == len(self.data):
                break
            record_id += 1
        return self._records

    def rebundle(self) -> bytes:
        raw = bytes(self.name.encode())
        raw += short_to_bytes(self.data_size)
        for group, records in self.records().items():
            for record in records:
                raw += record.rebundle()
        return raw

    def to_dict(self) -> dict[str, list[dict[str, ...]]]:
        result = defaultdict(list)
        for section, records in self.records().items():
            for record in records:
                result[str(section)].append(record.to_dict())
        result["file version"] = self.version
        return dict(result)

    def to_json(self) -> str:
        class BytesToHexEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, bytes):
                    return o.hex()
                return super().default(o)

        return json.dumps(self.to_dict(), indent=4, cls=BytesToHexEncoder)


param_format_lookup = {
    1: "Single byte",
    2: "2Byte,7Bits,hi->lo",
    3: "2Byte,7Bits,lo->hi",
    4: "3Byte,7Bits,lo->hi",
    5: "3Byte,7Bits,hi->lo",
    6: "2Byte, Nibs,hi->lo",
    7: "2Byte, Nibs,lo->hi",
    8: "3Byte, Nibs,hi->lo",
    9: "3Byte, Nibs,lo->hi",
    10: "4Byte, Nibs,hi->lo",
    11: "4Byte, Nibs,lo->hi",
    12: "2Byte,BCD Nibs,hi->lo",
    13: "2Byte,BCD Nibs,lo-hi",
}


fader_types = {
    0: Disabled,
    1: CC,
    2: Master,
    3: String,
}

button_types = {
    0: Disabled,
    1: Mute,
    2: Solo,
    3: ProgramChange,
    4: NoteOnOff,
    5: ButtonString,
    6: StringPressRelease,
    7: StringToggle,
    8: SendFader,
    9: SendScene,

}

data_wheel_types = {
    0: Disabled,
    1: DataWheel,
}

setup_types = {
    0: Disabled,
    1: Setup,
}


def record_factory(data: Data, section: Section):
    record_type = data[0] & 15
    if section in (Section.FADER, Section.CV):
        return fader_types[record_type](data=data, section=section)
    elif section == Section.BUTTON:
        return button_types[record_type](data=data, section=section)
    elif section == Section.DATA_WHEEL:
        return data_wheel_types[record_type](data=data, section=section)
    elif section == Section.SETUP:
        return setup_types[record_type](data=data, section=section)


def nibbles_to_int(c1: int, c2: int) -> int:
    return (c1 << 4) + c2


def short_to_bytes(b: int) -> bytes:
    return bytes([b >> 8, b & 0xff])


def int_to_nibbles(b: int) -> bytes:
    return bytes([b >> 4, b & 0xf])


def pack(data: Data):
    # sysex header
    output = b"\xf0\x00\x00\x1b\x0b\x00\x04"
    for x in data:
        output += int_to_nibbles(x)
    # sysex footer
    output += b"\xf7"
    return output


def unpack(data: bytes):
    # sysex header
    if data[0:5] != b"\xf0\x00\x00\x1b\x0b":
        print(f"ERROR: Invalid fingerprint! [{data[0:5]}]")
        exit()
    # data[5] == midi channel
    if data[6] == 0x01:  # All presets
        print("ERROR: 'All presets' sysex bundle not currently supported!")
        exit()
    if data[6] != 0x04:  # Current buffer
        print(f"Only buffer dumps are currently supported! [{data[6]}]")
        exit()
    # sysex footer
    assert data[-1] == 0xF7
    return Data(
        [
            nibbles_to_int(data[x], data[x + 1])
            for x in range(7, len(data) - 1, 2)
        ]
    )


@simplecli.wrap
def main(filename: str) -> None:
    with Path(filename).open("rb") as f:
        data = f.read()
    print(filename)
    patch = Patch(data)
    print(f"Patch: '{patch.name}'")
    print(patch.to_json())
