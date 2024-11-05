from pc1600.data import Data


def nibbles_to_int(c1: int, c2: int) -> int:
    return (c1 << 4) + c2


def int_to_nibbles(b: int) -> bytes:
    return bytes([b >> 4, b & 0xf])


def short_to_bytes(b: int) -> bytes:
    return bytes([b >> 8, b & 0xff])


def pack_sysex(data: Data, global_channel: int = 0) -> bytearray:
    # sysex header
    output = bytearray(b"\xf0\x00\x00\x1b\x0b")
    output.append(global_channel)
    output.append(4)
    for x in data:
        output += int_to_nibbles(x)
    # sysex footer
    output += b"\xf7"
    return output


def unpack_sysex(data: bytes):
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
    if data[-1] != 0xF7:
        print(f"ERROR: Invalid final byte! [{data[-1]}]")
        exit()
    raw_unpacked = [
        nibbles_to_int(data[i], data[i + 1])
        for i in range(7, len(data) - 1, 2)
    ]
    return Data(raw_unpacked)


def bitmap_ids(a: int, b: int) -> list[int]:
    return (
        [i+1 for i in range(8) if 0x1 & a >> i]
        + [i+9 for i in range(8) if 0x1 & b >> i]
    )
