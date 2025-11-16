import simplecli
import sys
from pathlib import Path
from pc1600 import sysex_file_to_sysex_patch


@simplecli.wrap
def main(
    sysex_file: str,
    json_file: str,
    debug: bool = False,
) -> None:
    json_path = Path(json_file)
    if json_path.is_file():
        print(f"ERROR: Output file '{json_path}' already exists!")
        sys.exit()
    patch = sysex_file_to_sysex_patch(sysex_file)
    if debug:
        print(patch.flatten())
    data = patch.to_json()
    with json_path.open("w", encoding="utf-8") as f:
        f.write(data)
    print(f"Wrote {len(data)} to {json_path}")
