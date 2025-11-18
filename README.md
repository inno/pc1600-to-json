# pc1600-to-json

## What

A library to parse and build PC1600 sysex dumps as well as a few command-line helpers to convert PC1600 sysex files to a JSON file and back again.

## Why

Making a new PC1600 patch is a very slow process. This allows any text editor to quickly build complicated patches without menu diving.

## Examples

### Convert sysex to JSON

```bash
python3 to_json.py 1600_MC303.syx MC303.json
```

### Convert JSON to sysex

```bash
python3 from_json.py MC303.json 1600_MC303_v2.syx
```

## Library

[pc1600](pc1600/__init__.py)
