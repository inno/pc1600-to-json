import simplecli
from pathlib import Path
from pc1600 import Patch


@simplecli.wrap
def main(
    syx_file: str,
    json_file: str,
    debug: bool = False,
    verbose: bool = False,
) -> None:
    json_path = Path(json_file)
    if json_path.is_file():
        print(f"ERROR: Output file '{json_path}' already exists!")
        exit()
    with Path(syx_file).open("rb") as f:
        data = f.read()
    patch = Patch(data)
    if verbose:
        for record in patch.records():
            print(record.section, record)
    if debug:
        print(patch.rebundle())
    data = patch.to_json()
    with json_path.open("w") as f:
        f.write(data)
    print(f"Wrote {len(data)} to {json_path}")
