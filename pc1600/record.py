import struct
from dataclasses import dataclass
from pc1600.data import Data
from pc1600.utils import (
    bitmap_ids,
    int_to_nibbles,
    nibbles_to_int,
    short_to_bytes,
)


@dataclass
class Record:
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
        return int_to_nibbles(self.data[0])[0]

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
class Disabled(Record):
    _type = 0
    _name_offset = 0

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00")


@dataclass
class CC(Record):
    _type = 1

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 32)  # Pre-pad with null
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        self.data[1] = fields["min"]
        self.data[2] = fields["max"]
        self.data[3] = fields["channel"]
        self.data[4] = fields["cc"]
        self.data[5] = fields["mode"]
        i = 0
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, 6 + i + 1)

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
class Master(Record):
    _type = 2
    _name_length = 0
    _name_offset = 0

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 1000)  # Pre-pad with null
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        val = sum([2 ** (v - 1) for v in fields["faders"]])
        data = short_to_bytes(val)
        self.data[1] = data[1]
        self.data[2] = data[0]
        self.data = self.data.bytearray(0, 3 + 1)

    @property
    def faders(self):
        return bitmap_ids(self.data[1], self.data[2])


@dataclass
class String(Record):
    _type = 3

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 1000)  # Pre-pad with null
        name = fields.get("name", "")
        sysex = bytes.fromhex(fields["sysex"])
        self.data[0] = nibbles_to_int(len(name), self._type)
        self.data[1] = param_format_inversion[fields["param_format"]]
        self.data[2:3] = struct.pack(">h", fields["min"])
        self.data[4:5] = struct.pack(">h", fields["max"])
        self.data[6] = len(sysex)
        i = 0
        for i in range(self._sysex_length):
            self.data[7 + i] = sysex[i]
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, 7 + self._sysex_length + i + 1)

    @property
    def _name_offset(self):
        return 7 + self._sysex_length

    @property
    def param_format(self):
        return param_format_lookup[self.data[1]]

    @property
    def _sysex_length(self) -> int:
        return self.data[6]

    @property
    def sysex(self) -> int:
        return self.data.bytearray(7, self._sysex_length)

    @property
    def min(self) -> int:
        return self.data.short(2)

    @property
    def max(self) -> int:
        return self.data.short(4)


@dataclass
class Mute(Record):
    _type = 1
    _name_offset = 1

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 100)
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        i = 0
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)


@dataclass
class Solo(Record):
    _type = 2
    _name_offset = 1

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 100)
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        i = 0
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)


@dataclass
class ProgramChange(Record):
    _type = 3
    _name_offset = 3

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 100)
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        self.data[1] = fields["channel"]
        self.data[2] = fields["program"]
        i = 0
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)

    @property
    def channel(self):
        return self.data[1]

    @property
    def program(self):
        return self.data[2]


@dataclass
class NoteOnOff(Record):
    _type = 4
    _name_offset = 4

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 100)
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        self.data[1] = fields["channel"]
        self.data[2] = fields["note"]
        self.data[3] = fields["velocity"]
        i = 0
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)

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
class ButtonString(Record):
    _type = 5

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 1000)  # Pre-pad with null
        name = fields.get("name", "")
        sysex = bytes.fromhex(fields["sysex"])
        self.data[0] = nibbles_to_int(len(name), self._type)
        self.data[1] = len(sysex)
        for i in range(self._sysex_length):
            self.data[2 + i] = sysex[i]
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)

    @property
    def _name_offset(self):
        return 2 + self._sysex_length

    @property
    def _sysex_length(self) -> int:
        return self.data[1]

    @property
    def sysex(self) -> int:
        return self.data.bytearray(2, self._sysex_length)


@dataclass
class StringPressRelease(Record):
    _type = 6

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 1000)  # Pre-pad with null
        name = fields.get("name", "")
        press = bytes.fromhex(fields["press"])
        release = bytes.fromhex(fields["release"])
        self.data[0] = nibbles_to_int(len(name), self._type)
        self.data[1] = len(press)
        for i in range(self._press_length):
            self.data[2 + i] = press[i]
        self.data[self._release_offset - 1] = len(release)
        for i in range(self._release_length):
            self.data[self._release_offset + i] = release[i]
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)

    @property
    def _name_offset(self) -> int:
        return self._release_offset + self._release_length

    @property
    def press(self) -> bytes:
        return self.data.bytearray(2, self._press_length)

    @property
    def _press_length(self) -> int:
        return self.data[1]

    @property
    def release(self) -> bytes:
        return self.data.bytearray(self._release_offset, self._release_length)

    @property
    def _release_length(self) -> int:
        return self.data[self._release_offset - 1]

    @property
    def _release_offset(self) -> int:
        return self._press_length + 3


@dataclass
class StringToggle(Record):
    _type = 7

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 1000)  # Pre-pad with null
        name = fields.get("name", "")
        sysex1 = bytes.fromhex(fields["sysex1"])
        sysex2 = bytes.fromhex(fields["sysex2"])
        self.data[0] = nibbles_to_int(len(name), self._type)
        self.data[1] = len(sysex1)
        for i in range(self._sysex1_length):
            self.data[2 + i] = sysex1[i]
        self.data[self._sysex2_offset - 1] = len(sysex2)
        for i in range(self._sysex2_length):
            self.data[self._sysex2_offset + i] = sysex2[i]
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)

    @property
    def _sysex1_length(self) -> int:
        return self.data[1]

    @property
    def sysex1(self) -> bytes:
        return self.data.bytearray(2, self._sysex1_length)

    @property
    def _sysex2_offset(self) -> int:
        return self._sysex1_length + 3

    @property
    def sysex2(self) -> bytes:
        return self.data.bytearray(self._sysex2_offset, self._sysex2_length)

    @property
    def _sysex2_length(self) -> int:
        return self.data[self._sysex2_offset - 1]

    @property
    def _name_offset(self) -> int:
        return self._sysex2_offset + self._sysex2_length


@dataclass
class SendFader(Record):
    _type = 8
    _name_offset = 1

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 100)
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        i = 0
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)


@dataclass
class SendScene(Record):
    _type = 9
    _name_offset = 1

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 100)
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        self.data[1] = fields["value"]
        i = 0
        for i in range(self._name_length):
            self.data[self._name_offset + i] = ord(name[i])
        self.data = self.data.bytearray(0, self._name_offset + i + 1)

    @property
    def value(self):
        return self.data[1]


@dataclass
class DataWheel(Record):
    _type = 1
    _name_offset = 0

    def __post_init__(self) -> None:
        self._wheel_lookup = {i: f"Fader {i+1}" for i in range(16)}
        self._wheel_lookup[16] = "CV 1"
        self._wheel_lookup[17] = "CV 2"
        self._wheel_lookup[18] = "Last fader"

    def pack(self, fields: dict[str, ...]) -> None:
        self.data = Data(b"\x00" * 4)  # Pre-pad with null
        wheel_reverse = {v: k for k, v in self._wheel_lookup.items()}
        self.data[0] = nibbles_to_int(0, self._type)
        self.data[1] = wheel_reverse[fields["mapped_to"]]
        self.data = self.data.bytearray(0, 2)

    @property
    def mapped_to(self):
        return self._wheel_lookup[self.data[1]]


@dataclass
class Setup(Record):
    _type = 1
    _name_offset = 0

    def pack(self, fields: dict[str, ...]) -> None:
        def seven_bit_reverse(value: str | int) -> int:
            return 0x7f if value == "Off" else value + 0x80

        def folded_reverse(value: str | int) -> int:
            if isinstance(value, str) and value.endswith("m"):
                return int(value[:-1]) - 1
            return value + 0x80

        self.data = Data(b"\x00" * 32)  # Pre-pad with null
        name = fields.get("name", "")
        self.data[0] = nibbles_to_int(len(name), self._type)
        offset = 3
        channels = fields.get("channels")
        if channels is not None:
            # midi channels
            val = sum([2 ** (int(v) - 1) for v in channels.keys()])
            data = short_to_bytes(val)
            self.data[1] = data[1]
            self.data[2] = data[0]

            for chd in channels.values():
                self.data[offset] = folded_reverse(chd["bank"])
                self.data[offset + 1] = seven_bit_reverse(chd["program"])
                self.data[offset + 2] = seven_bit_reverse(chd["volume"])
                offset += 3

        scene = fields.get("scene", None)
        if scene is not None:
            self.data[self._scene_offset] = 0xfe
            self.data[self._scene_offset + 1] = scene
            offset += 2

        sysex = fields["sysex"]
        if sysex is not None:
            sysex = bytes.fromhex(fields["sysex"])
            self.data[self._sysex_offset] = len(sysex)
            for i in range(len(sysex)):
                self.data[self._sysex_offset + i + 1] = sysex[i]
            offset += self._sysex_length
        self.data = self.data.bytearray(0, offset + 1)

    @property
    def _midi_channels(self):
        return bitmap_ids(self.data[1], self.data[2])

    @property
    def channels(self):
        def seven_bit(value) -> str | int:
            return value - 0x80 if value & 0x80 else "Off"

        def folded(value) -> str | int:
            return value - 0x80 if value & 0x80 else f"{value + 1}m"

        channels = {}
        offset = 3
        for channel in self._midi_channels:
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

param_format_inversion = {v: k for k, v in param_format_lookup.items()}
