import contextlib
import filecmp
import from_json
import to_json
from pathlib import Path


def flush_buffers(root: Path) -> None:
    buffers = ["outfile.json", "outfile.syx"]
    for buffer in buffers:
        file = root / buffer
        with contextlib.suppress(FileNotFoundError):
            file.unlink()


def test_regressions(tmp_path: Path) -> None:
    sysex_files = list(Path("tests/regressions").glob("*.syx"))
    flush_buffers(tmp_path)
    tmp_json_file = tmp_path / "outfile.json"
    tmp_sysex_file = tmp_path / "outfile.syx"
    for sysex_file in sysex_files:
        to_json.main(sysex_file=sysex_file, json_file=tmp_json_file)
        from_json.main(
            json_file=tmp_json_file,
            sysex_file=tmp_sysex_file,
        )
        comparison = filecmp.cmp(sysex_file, tmp_sysex_file, shallow=False)
        assert comparison, "File conversion syx -> json -> syx"
        flush_buffers(tmp_path)
