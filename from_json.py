import json
import simplecli
from dataclasses import dataclass
from pathlib import Path
from pc1600.record import (
    button_types,
    fader_types,
    setup_types,
    data_wheel_types,
)
from pc1600.patch import Patch, Section
from pc1600.utils import short_to_bytes, pack_sysex

button_records = {v.__name__: v for k, v in button_types.items()}
fader_records = {v.__name__: v for k, v in fader_types.items()}
data_wheel_records = {v.__name__: v for k, v in data_wheel_types.items()}
setup_records = {v.__name__: v for k, v in setup_types.items()}


# XXX This was a PoC. Integrate this with pc1600.patch.Patch!
def pack_patch(
    name: str,
    global_channel: int,
    faders: list[dict[str, ...]],
    cvs: list[dict[str, ...]],
    buttons: list[dict[str, ...]],
    data_wheel: list[dict[str, ...]],
    setup: list[dict[str, ...]],
):
    records = []
    for fader in faders:
        record = fader_records[fader["type"]]
        records.append(record.pack(fader, Section.FADER))

    for cv in cvs:
        record = fader_records[cv["type"]]
        records.append(record.pack(cv, Section.CV))

    for button in buttons:
        record = button_records[button["type"]]
        records.append(record.pack(button, Section.BUTTON))

    for wheel in data_wheel:
        record = data_wheel_records[wheel["type"]]
        records.append(record.pack(wheel, Section.DATA_WHEEL))

    for setup in setup:
        record = setup_records[setup["type"]]
        records.append(record.pack(setup, Section.SETUP))

    raw = b"".join([r.rebundle() for r in records])
    unpacked = (
        bytes(name.encode()).ljust(16)
        + short_to_bytes(len(raw))
        + raw
    )
    packed = pack_sysex(unpacked, global_channel=global_channel)
    return Patch(packed)


@simplecli.wrap
def main(
    json_file: str,
    syx_file: str,
    debug: bool = False,
) -> None:
    syx_path = Path(syx_file)
    if syx_path.is_file():
        print(f"ERROR: Output file '{syx_path}' already exists!")
        exit()
    with Path(json_file).open("r") as f:
        data = json.load(f)

    # file_version = data["file version"]
    patch = pack_patch(
        name=data["name"],
        global_channel=data["global_channel"],
        faders=data["fader"],
        cvs=data["cv"],
        buttons=data["button"],
        data_wheel=data["data wheel"],
        setup=data["setup"],
    )
    data = patch.to_syx()
    with Path(syx_file).open("wb") as f:
        f.write(data)
    print(f"Wrote {len(data)} bytes to {syx_file}")
