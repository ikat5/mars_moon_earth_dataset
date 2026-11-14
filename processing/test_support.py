"""Test helpers: data-dependent tests skip cleanly in checkouts without Git LFS objects (e.g. CI)."""
from pathlib import Path


def has_release_data(data_dir):
    """True when every Parquet table in data_dir is real data, not a missing file or Git LFS pointer."""
    tables = list(Path(data_dir).glob("*.parquet"))
    if not tables:
        return False
    for table in tables:
        with open(table, "rb") as f:
            if f.read(4) != b"PAR1":
                return False
    return True
