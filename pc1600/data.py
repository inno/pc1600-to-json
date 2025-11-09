import struct
from pc1600.utils import int_to_nibbles, nibbles_to_int


class UnsupportedFormatError(Exception):
    pass

class Data(bytearray):
    def short(self, offset: int) -> int:
        return struct.unpack(">h", self[offset: offset + 2])[0]

    def bytearray(self, offset: int, length: int) -> "Data":
        return Data(self[offset:offset + length])

    def string(self, offset: int, length: int) -> str:
        if length == 0:
            return ""
        result = ""
        for c in self.bytearray(offset, length):
            if c < 32 or 126 < c:
                msg = (
                    "ERROR: "
                    f"Invalid character detected! [{hex(c)}] "
                    "Either we have processed a record wrong "
                    "or the file is corrupt. "
                    f"Attempt to stringify {self.bytearray(offset, length)}",
                )
                raise UnsupportedFormatError(msg)
            result += chr(c)
        return result

    def debug(self, length: None | int = None) -> None:
        print("### DEBUG ###")
        if length is None:
            length = len(self)
        for i in range(length):
            char = "" if self[i] < 32 or 126 < self[i] else chr(self[i])
            print(f"{i}:\t{self[i]}\t{hex(self[i])}\t{char}")



# Automatically handle mixing bytes and lists of ints
def data_factory(*args) -> Data:
    data = Data()
    for arg in args:
        data.extend(arg if isinstance(arg, bytes) else [arg])
    return data


def pack_sysex(raw: bytes, global_channel: int = 0) -> bytearray:
    # sysex header
    output = bytearray(b"\xf0\x00\x00\x1b\x0b")
    output.append(global_channel)
    output.append(4)
    output.extend([nibble for i in raw for nibble in int_to_nibbles(i)])
    # sysex footer
    output += b"\xf7"
    return output


def unpack_sysex(data: bytes) -> Data:
    # sysex header
    if data[0:5] != b"\xf0\x00\x00\x1b\x0b":
        msg = f"ERROR: Invalid fingerprint! [{data[0:5].decode()}]"
        raise UnsupportedFormatError(msg)
    # data[5] == midi channel
    if data[6] == 0x01:  # All presets
        msg = "'All presets' sysex bundle not currently supported!"
        raise UnsupportedFormatError(msg)
    if data[6] != 0x04:  # Current buffer
        msg = f"Only buffer dumps are currently supported! [{data[6]}]"
        raise UnsupportedFormatError(msg)
    # sysex footer
    if data[-1] != 0xF7:
        msg = f"Invalid final byte! [{data[-1]}]"
        raise UnsupportedFormatError(msg)
    raw_unpacked = [
        nibbles_to_int(data[i], data[i + 1])
        for i in range(7, len(data) - 1, 2)
    ]
    return Data(raw_unpacked)
