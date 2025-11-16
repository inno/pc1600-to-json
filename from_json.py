import simplecli
import sys
from pathlib import Path
from pc1600 import json_file_to_sysex_patch


@simplecli.wrap
def main(
    json_file: str,
    sysex_file: str,
) -> None:
    sysex_path = Path(sysex_file)
    if sysex_path.is_file():
        print(f"ERROR: Output file '{sysex_path}' already exists!")
        sys.exit()
    patch = json_file_to_sysex_patch(json_file)
    raw_sysex = patch.to_raw_sysex()
    with Path(sysex_file).open("wb") as f:
        f.write(raw_sysex)
    print(f"Wrote {len(raw_sysex)} bytes to {sysex_file}")
