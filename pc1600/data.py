import struct


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
