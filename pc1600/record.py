import struct
from dataclasses import dataclass
from pc1600.data import Data, data_factory
from pc1600.utils import (
    bitmap_ids,
    int_to_nibbles,
    nibbles_to_int,
    short_to_bytes,
)
from typing import ClassVar

Fields = dict[str, int | str]

@dataclass
class Field:
    type: int

@dataclass(kw_only=True)
class NamedFields(Field):
    name: str = ""

@dataclass
class ProgramFields(NamedFields):
    channel: int
    program: int

@dataclass
class StringFields(NamedFields):
    sysex: str
    param_format: str
    min: int
    max: int

@dataclass
class MasterFields(NamedFields):
    faders: list[int]
    wut: int

@dataclass
class CCFields(NamedFields):
    min: int
    max: int
    channel: int
    cc: int
    mode: int

@dataclass
class NoteOnOffFields(NamedFields):
    channel: int
    note: int
    velocity: int

@dataclass
class ButtonStringFields(NamedFields):
    sysex: str

@dataclass
class StringPressReleaseFields(NamedFields):
    press: str
    release: str

@dataclass
class StringToggleFields(NamedFields):
    sysex1: str
    sysex2: str

@dataclass
class SendFaderFields(NamedFields):
    pass

@dataclass
class SendSceneFields(NamedFields):
    value: int

@dataclass
class DataWheelFields(Field):
    mapped_to: str

@dataclass
class SetupFields(NamedFields):
    channels: dict[int, dict[str, str | int]] | None = None
    scene: int | None = None
    sysex: str | None = None

@dataclass
class Record:
    section: str
    data: Data
    _type: ClassVar[int] = -1

    def __str__(self) -> str:
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

    def to_dict(self) -> dict[str, str]:
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

    def length(self) -> int:
        return len(self.data)

    def rebundle(self) -> bytes:
        return bytes([self.length()]) + self.data[:self.length()]

    @property
    def type_and_name_length(self) -> int:
        return nibbles_to_int(self._type, len(self.name))

    @classmethod
    def _pack(cls, data: Data, length: int = 0, section: str = "") -> "Record":
        if length == 0:
            return cls(data=data, section=section)
        return cls(data=data.bytearray(0, length), section=section)


@dataclass
class Disabled(Record):
    _type: ClassVar[int] = 0

    @property
    def _name_offset(self) -> int:
        return 0

    @classmethod
    def pack(cls, _: Fields, section: str) -> "Disabled":
        return cls(data=data_factory(b"\x00"), section=section)


@dataclass
class CC(Record):
    _type: ClassVar[int] = 1

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "CC":
        cc_fields = CCFields(**fields)
        data = data_factory(
            nibbles_to_int(len(cc_fields.name), cls._type),
            cc_fields.min,
            cc_fields.max,
            cc_fields.channel,
            cc_fields.cc,
            cc_fields.mode,
            cc_fields.name.encode(),
        )
        return cls(data=data, section=section)

    @property
    def min(self) -> int:
        return self.data[1]

    @property
    def max(self) -> int:
        return self.data[2]

    # gc = global channel (0xFE?)
    # -gc = channelized previous byte  (0xFE)
    # dv = device number   (0xFD)
    # rv = remote velocity (0xFF)

    @property
    def channel(self) -> int:
        return self.data[3]

    @property
    def cc(self) -> int:
        return self.data[4]

    @property
    def mode(self) -> int:
        return self.data[5]


@dataclass
class Master(Record):
    _type: ClassVar[int] = 2

    @property
    def _name_offset(self) -> int:
        return 4

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "Master":
        master_fields = MasterFields(**fields)
        val = sum(2 ** (v - 1) for v in master_fields.faders)
        val_data = short_to_bytes(val)
        data = data_factory(
            nibbles_to_int(len(master_fields.name), cls._type),
            val_data[1],
            val_data[0],
            master_fields.wut,
            master_fields.name.encode(),
        )
        return cls(data=data, section=section)

    @property
    def faders(self) -> list[int]:
        return bitmap_ids(self.data[1], self.data[2])

    # Seems to be "3" sometimes...?
    @property
    def wut(self) -> int:
        return self.data[3]


@dataclass
class String(Record):
    _type: ClassVar[int] = 3

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "String":
        string_fields = StringFields(**fields)
        sysex = bytes.fromhex(string_fields.sysex)
        data = data_factory(
            nibbles_to_int(len(string_fields.name), cls._type),
            param_format_inversion[string_fields.param_format],
            struct.pack(">h", string_fields.min),
            struct.pack(">h", string_fields.max),
            len(sysex),
            sysex,
            string_fields.name.encode(),
        )
        return cls(data=data, section=section)

    @property
    def _name_offset(self) -> int:
        return 7 + self._sysex_length

    @property
    def param_format(self) -> str:
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
    _type: ClassVar[int] = 1

    @property
    def _name_offset(self) -> int:
        return 1

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "Mute":
        mute_fields = NamedFields(**fields)
        data = data_factory(
            nibbles_to_int(len(mute_fields.name), cls._type),
            mute_fields.name.encode(),
        )
        return cls(data=data, section=section)


@dataclass
class Solo(Record):
    _type: ClassVar[int] = 2

    @property
    def _name_offset(self) -> int:
        return 1

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "Solo":
        solo_fields = NamedFields(**fields)
        data = data_factory(
            nibbles_to_int(len(solo_fields.name), cls._type),
            solo_fields.name.encode(),
        )
        return cls(data=data, section=section)


@dataclass
class ProgramChange(Record):
    _type: ClassVar[int] = 3

    @property
    def _name_offset(self) -> int:
        return 3

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "ProgramChange":
        program_fields = ProgramFields(**fields)
        data = data_factory(
            nibbles_to_int(len(program_fields.name), cls._type),
            program_fields.channel,
            program_fields.program,
            program_fields.name.encode(),
        )
        return cls(data=data, section=section)

    @property
    def channel(self) -> int:
        return self.data[1]

    @property
    def program(self) -> int:
        return self.data[2]


@dataclass
class NoteOnOff(Record):
    _type: ClassVar[int] = 4

    @property
    def _name_offset(self) -> int:
        return 4

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "NoteOnOff":
        note_on_off_fields = NoteOnOffFields(**fields)
        data = data_factory(
            nibbles_to_int(len(note_on_off_fields.name), cls._type),
            note_on_off_fields.channel,
            note_on_off_fields.note,
            note_on_off_fields.velocity,
            note_on_off_fields.name.encode(),
        )
        return cls(data=data, section=section)

    @property
    def channel(self) -> int:
        return self.data[1]

    @property
    def note(self) -> int:
        return self.data[2]

    @property
    def velocity(self) -> int:
        return self.data[3]


@dataclass
class ButtonString(Record):
    _type: ClassVar[int] = 5

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "ButtonString":
        button_string_fields = ButtonStringFields(**fields)
        sysex = bytes.fromhex(button_string_fields.sysex)
        data = data_factory(
            nibbles_to_int(len(button_string_fields.name), cls._type),
            len(sysex),
            sysex,
            button_string_fields.name.encode(),
        )
        return cls(data=data, section=section)

    @property
    def _name_offset(self) -> int:
        return 2 + self._sysex_length

    @property
    def _sysex_length(self) -> int:
        return self.data[1]

    @property
    def sysex(self) -> int:
        return self.data.bytearray(2, self._sysex_length)


@dataclass
class StringPressRelease(Record):
    _type: ClassVar[int] = 6

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "StringPressRelease":
        string_press_release_fields = StringPressReleaseFields(**fields)
        press = bytes.fromhex(string_press_release_fields.press)
        release = bytes.fromhex(string_press_release_fields.release)
        data = data_factory(
            nibbles_to_int(len(string_press_release_fields.name), cls._type),
            len(press),
            press,
            len(release),
            release,
            string_press_release_fields.name.encode(),
        )
        return cls(data=data, section=section)

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
    _type: ClassVar[int] = 7

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "StringToggle":
        string_toggle_fields = StringToggleFields(**fields)
        sysex1 = bytes.fromhex(string_toggle_fields.sysex1)
        sysex2 = bytes.fromhex(string_toggle_fields.sysex2)
        data = data_factory(
            nibbles_to_int(len(string_toggle_fields.name), cls._type),
            len(sysex1),
            sysex1,
            len(sysex2),
            sysex2,
            string_toggle_fields.name.encode(),
        )
        return cls(data=data, section=section)

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
    _type: ClassVar[int] = 8

    @property
    def _name_offset(self) -> int:
        return 1

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "SendFader":
        send_fader_fields = SendFaderFields(**fields)
        data = data_factory(
            nibbles_to_int(len(send_fader_fields.name), cls._type),
            send_fader_fields.name.encode(),
        )
        return cls(data=data, section=section)


@dataclass
class SendScene(Record):
    _type: ClassVar[int] = 9

    @property
    def _name_offset(self) -> int:
        return 1

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "SendScene":
        send_scene_fields = SendSceneFields(**fields)
        data = data_factory(
            nibbles_to_int(len(send_scene_fields.name), cls._type),
            send_scene_fields.value,
            send_scene_fields.name.encode(),
        )
        return cls(data=data, section=section)

    @property
    def value(self) -> int:
        return self.data[1]


@dataclass
class DataWheel(Record):
    _type: ClassVar[int] = 1

    @property
    def _name_offset(self) -> int:
        return 0

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "DataWheel":
        data_wheel_fields = DataWheelFields(**fields)
        wheel_reverse = {v: k for k, v in wheel_lookup.items()}
        data = data_factory(
            nibbles_to_int(0, cls._type),
            wheel_reverse[data_wheel_fields.mapped_to],
        )
        return cls(data=data, section=section)

    @property
    def mapped_to(self) -> str:
        return wheel_lookup[self.data[1]]


@dataclass
class Setup(Record):
    _type: ClassVar[int] = 1

    @property
    def _name_offset(self) -> int:
        return 0

    @classmethod
    def pack(cls, fields: Fields, section: str) -> "Setup":
        def seven_bit_reverse(value: str | int) -> int:
            return 0x7f if value == "Off" else int(value) + 0x80

        def folded_reverse(value: str | int) -> int:
            if isinstance(value, str) and value.endswith("m"):
                return int(value[:-1]) - 1
            return int(value) + 0x80

        setup_fields = SetupFields(**fields)
        data = data_factory(nibbles_to_int(len(setup_fields.name), cls._type))
        channels = setup_fields.channels
        if channels:
            # midi channels
            val = sum(2 ** (int(v) - 1) for v in channels)
            val_data = short_to_bytes(val)
            data.extend([val_data[1], val_data[0]])

            for chd in channels.values():
                data.extend([
                    folded_reverse(chd["bank"]),
                    seven_bit_reverse(chd["program"]),
                    seven_bit_reverse(chd["volume"]),
                ])
        else:
            data.extend([0x00, 0x00])

        scene = setup_fields.scene
        if scene:
            data.extend([0xfe, scene])

        sysex = setup_fields.sysex
        if sysex:
            sysex = bytes.fromhex(setup_fields.sysex)
            data.extend([len(sysex)])
            data.extend(sysex)
        else:
            data.extend([0x00])
        return cls._pack(data=data, section=section)

    @property
    def _midi_channels(self) -> list[int]:
        return bitmap_ids(self.data[1], self.data[2])

    @property
    def channels(self) -> dict[int, dict[str, str | int]]:
        def seven_bit(value: int) -> str | int:
            return value - 0x80 if value & 0x80 else "Off"

        def folded(value: int) -> str | int:
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
    def scene(self) -> None | int:
        if not self._has_scene:
            return None
        return self.data[self._scene_offset + 1]

    @property
    def _sysex_length(self) -> int:
        return self.data[self._sysex_offset]

    @property
    def sysex(self) -> Data | None:
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

name_to_fader_id = {v.__name__: v for k, v in fader_types.items()}
name_to_button_id = {v.__name__: v for k, v in button_types.items()}
name_to_data_wheel_id = {v.__name__: v for k, v in data_wheel_types.items()}
name_to_setup_id = {v.__name__: v for k, v in setup_types.items()}

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

wheel_lookup = {i: f"Fader {i+1}" for i in range(16)}
wheel_lookup[16] = "CV 1"
wheel_lookup[17] = "CV 2"
wheel_lookup[18] = "Last fader"
