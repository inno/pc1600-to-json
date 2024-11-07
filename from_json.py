import json
import simplecli
from pathlib import Path
from pc1600 import json_to_patch


@simplecli.wrap
def main(
    json_file: str,
    syx_file: str,
    verbose: bool = False,
) -> None:
    syx_path = Path(syx_file)
    if syx_path.is_file():
        print(f"ERROR: Output file '{syx_path}' already exists!")
        exit()
    with Path(json_file).open("r") as f:
        data = json.load(f)

    patch = json_to_patch(verbose=verbose, **data)
    data = patch.to_syx()
    with Path(syx_file).open("wb") as f:
        f.write(data)
    print(f"Wrote {len(data)} bytes to {syx_file}")
