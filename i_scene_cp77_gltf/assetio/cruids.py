from __future__ import annotations

import random


def new_cruid(taken: set[str], rng: random.Random | None = None) -> str:
    """A random non-zero 63-bit id not in taken, added to taken"""
    generator = rng or random.SystemRandom()
    while True:
        value = str(generator.randrange(1, 2**63))
        if value not in taken:
            taken.add(value)
            return value


def rebuild_cruid_dict(package_data: dict) -> None:
    """Set the package's id dictionary from its chunks' ids, in chunk order"""
    package_data["CruidDict"] = {
        str(index): chunk["id"]
        for index, chunk in enumerate(package_data.get("Chunks") or ())
        if isinstance(chunk, dict) and "id" in chunk
    }
