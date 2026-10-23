"""Access to the Avro schemas under `contracts/`.

The schemas are not vendored into this package: there is exactly one copy, at
the repo root, and the producer, Flink and ClickHouse all agree with it or fail
loudly. Set MDP_CONTRACTS_DIR to point elsewhere (containers, tests).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_SCHEMA_SUBPATH = Path("market") / "v1"


def contracts_dir() -> Path:
    override = os.environ.get("MDP_CONTRACTS_DIR")
    if override:
        return Path(override)
    # Walk up from this file until a directory holding the schemas appears.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "contracts"
        if (candidate / _SCHEMA_SUBPATH).is_dir():
            return candidate
    raise FileNotFoundError("Could not locate the contracts/ directory. Set MDP_CONTRACTS_DIR.")


@lru_cache
def load_schema(name: str) -> str:
    """Return the raw Avro schema text, e.g. load_schema('tick')."""
    path = contracts_dir() / _SCHEMA_SUBPATH / f"{name}.avsc"
    if not path.is_file():
        raise FileNotFoundError(f"No Avro schema at {path}")
    return path.read_text()
