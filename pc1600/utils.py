from __future__ import annotations


class UnsupportedFormatError(Exception):
    pass


def nibbles_to_int(c1: int, c2: int) -> int:
    return (c1 << 4) + c2


def int_to_nibbles(b: int) -> bytes:
    return bytes([b >> 4, b & 0xf])  # fmt: skip


def short_to_bytes(b: int) -> bytes:
    return bytes([b >> 8, b & 0xff])  # fmt: skip


def bitmap_ids(a: int, b: int) -> list[int]:
    return [i + 1 for i in range(8) if 0x1 & a >> i] + [
        i + 9 for i in range(8) if 0x1 & b >> i
    ]


def pack_sysex(raw: bytes, global_channel: int = 0) -> bytearray:
    # sysex header
    output = bytearray(b"\xf0\x00\x00\x1b\x0b")
    output.append(global_channel)
    output.append(4)
    output.extend([nibble for i in raw for nibble in int_to_nibbles(i)])
    # sysex footer
    output += b"\xf7"
    return output


def unpack_sysex(data: bytes) -> list[int]:
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
    return [
        nibbles_to_int(data[i], data[i + 1])
        for i in range(7, len(data) - 1, 2)
    ]
