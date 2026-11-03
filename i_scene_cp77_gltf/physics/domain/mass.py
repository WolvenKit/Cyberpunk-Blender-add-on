from __future__ import annotations

MASS_KEYS = ("massOverride", "mass")


def positive_mass(*records):
    """The first positive massOverride or mass among records, or 0.0"""
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in MASS_KEYS:
            try:
                value = float(record.get(key))
            except (TypeError, ValueError):
                continue
            if value > 0.0:
                return value
    return 0.0
