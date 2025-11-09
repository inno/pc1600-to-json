def nibbles_to_int(c1: int, c2: int) -> int:
    return (c1 << 4) + c2


def int_to_nibbles(b: int) -> bytes:
    return bytes([b >> 4, b & 0xf])


def short_to_bytes(b: int) -> bytes:
    return bytes([b >> 8, b & 0xff])


def bitmap_ids(a: int, b: int) -> list[int]:
    return (
        [i+1 for i in range(8) if 0x1 & a >> i]
        + [i+9 for i in range(8) if 0x1 & b >> i]
    )
