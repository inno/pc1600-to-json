import simplecli
from pathlib import Path
from pc1600 import Patch


@simplecli.wrap
def main(
    syx_file: str,
    json_file: str,
) -> None:
    json_path = Path(json_file)
    if json_path.exists():
        print(f"ERROR: Output file '{json_path}' already exists!")
        exit()
    with Path(syx_file).open("rb") as f:
        data = f.read()
    patch = Patch(data)
    data = patch.to_json()
    with json_path.open("w") as f:
        f.write(data)
    print(f"Wrote {len(data)} to {json_path}")
