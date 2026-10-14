from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin"


def find(name):
    return next(iter([*BIN.glob(name), *BIN.glob(f"*/{name}")]))
