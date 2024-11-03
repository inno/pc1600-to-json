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
from pc1600.patch import Section
from pc1600.utils import short_to_bytes, pack_sysex

button_records = {v.__name__: v for k, v in button_types.items()}
fader_records = {v.__name__: v for k, v in fader_types.items()}
data_wheel_records = {v.__name__: v for k, v in data_wheel_types.items()}
setup_records = {v.__name__: v for k, v in setup_types.items()}


@dataclass
class Patch:
    name: str
    faders: list[dict[str, ...]]
    cvs: list[dict[str, ...]]
    buttons: list[dict[str, ...]]
    data_wheel: list[dict[str, ...]]
    setup: list[dict[str, ...]]
    records: list[...] = None

    def process(self):
        self.records = []
        for fader in self.faders:
            func = fader_records[fader["type"]]
            record = func(section=Section.FADER, data=b"")
            record.pack(fader)
            self.records.append(record)

        for cv in self.cvs:
            func = fader_records[cv["type"]]
            record = func(section=Section.CV, data=b"")
            record.pack(cv)
            self.records.append(record)

        for button in self.buttons:
            func = button_records[button["type"]]
            record = func(section=Section.BUTTON, data=b"")
            record.pack(button)
            self.records.append(record)

        for wheel in self.data_wheel:
            func = data_wheel_records[wheel["type"]]
            record = func(section=Section.DATA_WHEEL, data=b"")
            record.pack(wheel)
            self.records.append(record)

        for setup in self.setup:
            func = setup_records[setup["type"]]
            record = func(section=Section.SETUP, data=b"")
            record.pack(setup)
            self.records.append(record)

    def rebundle(self) -> bytes:
        raw = b"".join([r.rebundle() for r in self.records])
        return (
            bytes(self.name.encode()).ljust(16)
            + short_to_bytes(len(raw))
            + raw
        )


@simplecli.wrap
def main(
    json_file: str,
    syx_file: str,
) -> None:
    syx_path = Path(syx_file)
    if syx_path.exists():
        print(f"ERROR: Output file '{syx_path}' already exists!")
        exit()
    with Path(json_file).open("r") as f:
        data = json.load(f)

    # file_version = data["file version"]
    patch = Patch(
        name=data["name"],
        faders=data["fader"],
        cvs=data["cv"],
        buttons=data["button"],
        data_wheel=data["data wheel"],
        setup=data["setup"],

    )
    patch.process()
    data = pack_sysex(patch.rebundle())
    with Path(syx_file).open("wb") as f:
        f.write(data)
    print(f"Wrote {len(data)} bytes to {syx_file}")
