import simplecli
from pathlib import Path
from pc1600 import Patch


@simplecli.wrap
def main(filename: str) -> None:
    with Path(filename).open("rb") as f:
        data = f.read()
    patch = Patch(data)
    print(patch.to_json())
