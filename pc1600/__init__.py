from pc1600.data import Data
from pc1600.patch import Patch, Section
from pc1600.record import (
    Record,
    name_to_fader_id,
    name_to_button_id,
    name_to_data_wheel_id,
    name_to_setup_id,
)
from pc1600.utils import pack_sysex, short_to_bytes, unpack_sysex


def json_to_patch(
    buttons: list[Record],
    cvs: list[Record],
    data_wheel: list[Record],
    faders: list[Record],
    file_version: str,
    global_channel: int,
    name: str,
    setup: list[Record],
    verbose: bool = False,
) -> Patch:
    sections = [
        (Section.FADERS, name_to_fader_id, faders),
        (Section.CVS, name_to_fader_id, cvs),
        (Section.BUTTONS, name_to_button_id, buttons),
        (Section.DATA_WHEEL, name_to_data_wheel_id, data_wheel),
        (Section.SETUP, name_to_setup_id, setup),
    ]

    raw = b""
    for record_type, lookup, section in sections:
        for item in section:
            record = lookup[item["type"]].pack(item, record_type)
            if verbose:
                print(record)
            raw += record.rebundle()
    unpacked = bytes(name.encode()).ljust(16)
    unpacked += short_to_bytes(len(raw))
    unpacked += raw
    if verbose:
        print("UNPACKED:", unpacked)
    packed = pack_sysex(unpacked, global_channel=global_channel)
    return Patch(packed)
