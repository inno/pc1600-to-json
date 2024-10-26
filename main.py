import simplecli
import struct
from dataclasses import dataclass
from pathlib import Path


BYTE = 0
NIB = 1
STR = 2

record_type_lookup = {
    0: "Disabled",
    1: "CC",  # Done?
    2: "Master",
    3: "String",
    4: "Note On/Off",

    # Button-specific
    5: "Button String",
    6: "String Prs/Rls",
    7: "String Toggle",
    8: "Send Fader",
    9: "Send Scene",
}

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


class Data(bytes):
    def short(self, offset: int) -> int:
        return struct.unpack(">h", self[offset: offset + 2])[0]

    def bytearray(self, offset: int = 0, length: int = 9999) -> bytes:
        return Data(self[offset:offset + length])

    def string(self, offset: int, length: int) -> str:
        if length == 0:
            return ""
        result = ""
        for c in self.bytearray(offset, length):
            if c < 32 or 126 < c:
                continue
                print(
                    "WARNING: "
                    f"Invalid character detected! [{hex(c)}] "
                    "Either we have processed a record wrong "
                    "or the file is corrupt. "
                    f"Attempt to stringify {self.bytearray(offset, length)}"
                )
            result += chr(c)
        return result

    def debug(self, offset: int = 0, length: None | int = None):
        if length is None:
            length = len(self) - 1
        for i in range(0, length):
            char = "" if self[i] < 32 or 126 < self[i] else chr(self[i])
            print(f"{i}:\t{self[i]}\t{hex(self[i])}\t{char}")


@dataclass
class Input:
    section: str
    data: Data

    def __str__(self):
        properties = []
        for prop in dir(self):
            if prop.startswith("__"):
                continue
            if prop == "data":
                continue
            if callable(getattr(self, prop)):
                continue
            properties.append(f"{prop}={getattr(self, prop)}")
        return f"{type(self).__name__}({', '.join(properties)})"

    def to_dict(self):
        result = {}
        for prop in dir(self):
            if prop in self.fields():
                result[prop] = getattr(self, prop)
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
        raise Exception("Subclass missing `length` method!")

    def rebundle(self):
        return self.data[:self.length()]


@dataclass
class Disabled(Input):
    type = 0
    _name_offset = 0

    def length(self):
        return 1


@dataclass
class CC(Input):
    type = 1

    def length(self):
        return 6 + self._name_length

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
    type = 2
    _name_length = 0
    _name_offset = 0

    def __post_init__(self):
        self.data.debug(length=self.length())

    def length(self):
        return 4 + self._name_length


@dataclass
class String(Input):
    type = 3

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
    def value(self) -> int:
        return self.data[7:self._string_length + 7]

    def length(self) -> int:
        return 7 + self._string_length + self._name_length

    @property
    def min(self) -> int:
        return self.data.short(2)

    @property
    def max(self) -> int:
        return self.data.short(4)


@dataclass
class Mute(Input):
    type = 1
    _name_offset = 1

    def length(self) -> int:
        return 1 + self._name_length


@dataclass
class Solo(Input):
    type = 2
    _name_offset = 1

    def length(self) -> int:
        return 1 + self._name_length


@dataclass
class ProgramChange(Input):
    type = 3
    _name_offset = 3

    def length(self) -> int:
        return 3 + self._name_length

    @property
    def channel(self):
        return self.data[1]

    @property
    def program(self):
        return self.data[2]


@dataclass
class NoteOnOff(Input):
    type = 4
    _name_offset = 4

    def __post_init__(self):
        self.data.debug(length=self.length())

    def length(self):
        return self._name_length + self._name_offset

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
    type = 5

    @property
    def _string_length(self) -> int:
        return self.data[1]

    @property
    def value(self) -> int:
        return self.data[2:self._string_length + 2]

    def length(self) -> int:
        return 2 + self._string_length + self._name_length


@dataclass
class StringPressRelease(Input):
    type = 6

    @property
    def _name_offset(self) -> int:
        return self._value2_offset + self._value2_length

    def length(self):
        return self._name_offset + self._name_length

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
    type = 7

    @property
    def _name_offset(self) -> int:
        return self._value2_offset + self._value2_length

    def length(self):
        return self._name_offset + self._name_length

    @property
    def value1(self) -> bytes:
        return self.data.bytearray(2, self._value1_length)

    @property
    def _value1_length(self) -> int:
        return self.data[1]

    @property
    def value2(self) -> bytes:
        return self.data.bytearray(self._value2_offset, self._value2_length)

    @property
    def _value2_length(self) -> int:
        return self.data[self._value2_offset - 1]

    @property
    def _value2_offset(self) -> int:
        return self._value1_length + 3


@dataclass
class SendFader(Input):
    type = 8


@dataclass
class SendScene(Input):
    type = 9


FADER_SECTION = "fader"
CV_SECTION = "cv"
BUTTON_SECTION = "button"


@dataclass
class Patch:
    data: Data
    _active_section: str = FADER_SECTION
    _record_id: int = 0
    _record_offset: int = 19

    @property
    def name(self) -> str:
        return self.data.string(0, 16)

    @property
    def size(self) -> int:
        return (self.data.short(17), self.data[17], self.data[18])

    def records(self) -> list[Input]:
        records = {
            FADER_SECTION: [],
            CV_SECTION: [],
            BUTTON_SECTION: [],
        }
        record_offset = 19
        curret_section = FADER_SECTION
        for record_id in range(16 + 2 + 16):
            if record_id == 16:
                curret_section = CV_SECTION
            elif record_id == 18:
                curret_section = BUTTON_SECTION
            record = record_factory(
                data=self.data.bytearray(record_offset),
                section=curret_section,
            )
            records[curret_section].append(record)
            record_offset += record.length() + 1
            record_id += 1
        return records


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
}


def record_factory(data: Data, section: int):
    record_type = data[0] & 15
    if section in ("fader", "cv"):
        return fader_types[record_type](data=data, section=section)
    elif section == "button":
        record = button_types.get(record_type)
        if record:
            return record(data=data, section=section)
        else:
            record = Input(data=data, section=section)
            try:
                record_desc = record_type_lookup[record_type]
            except KeyError:
                exit(
                    "ERROR: Either we have processed the above record "
                    "wrong or the file is corrupt!"
                )
            print(f"RECORD_TYPE={record_type} ({record_desc})")
            return record


def dump_to_patch(data: bytes):
    # sysex header
    assert data[0:6] == b"\xf0\x00\x00\x1b\x0b\x00"
    # sysex footer
    assert data[-1] == 0xF7
    unpacked = [data[x] * 16 + data[x + 1] for x in range(7, len(data) - 1, 2)]
    print("Patch length:", len(unpacked))
    return Patch(Data(unpacked))


def factory(data: bytes) -> Patch:
    patch = dump_to_patch(data)
    print(f"Patch: '{patch.name}'")
    print(f"Size (sometimes?): {patch.size}")
    records = patch.records()
    print(records)
    exit()
    # 16 x fader
    # 2 x CV
    # 16 x buttons
    # ...?
    print("#### Faders ####")
    for _ in range(16):
        r = patch.next_record()
        print(r)
        print(r.to_dict())
    print("#### CV ####")
    for _ in range(2):
        r = patch.next_record()
        print(r)
        print(r.to_dict())
    print("#### Buttons ####")
    for _ in range(16):
        r = patch.next_record()
        print(r)
        print(r.to_dict())
    return patch


@simplecli.wrap
def main(filename: str) -> None:
    with Path(filename).open("rb") as f:
        data = f.read()
    print(filename)
    factory(data)
