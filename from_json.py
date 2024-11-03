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

    def process(self):
        records = []
        for fader in self.faders:
            func = fader_records[fader["type"]]
            record = func(section=Section.FADER, data=b"")
            record.pack(fader)
            records.append(record)
            print(Section.FADER, record)

        for cv in self.cvs:
            func = fader_records[cv["type"]]
            record = func(section=Section.CV, data=b"")
            record.pack(cv)
            print(Section.CV, record)

        for button in self.buttons:
            func = button_records[button["type"]]
            record = func(section=Section.BUTTON, data=b"")
            record.pack(button)
            records.append(record)
            print(Section.BUTTON, record)

        for wheel in self.data_wheel:
            func = data_wheel_records[wheel["type"]]
            record = func(section=Section.DATA_WHEEL, data=b"")
            record.pack(wheel)
            records.append(record)
            print(Section.DATA_WHEEL, record)

        for setup in self.setup:
            func = setup_records[setup["type"]]
            record = func(section=Section.SETUP, data=b"")
            record.pack(setup)
            records.append(record)
            print(Section.SETUP, record)

        # for record in records:
        #     print(record)


@simplecli.wrap
def main(filename: str) -> None:
    with Path(filename).open("r") as f:
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
