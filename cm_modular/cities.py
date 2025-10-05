from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable

__all__ = ["City", "CityPresets"]

@dataclass(frozen=True)
class City:
    """Geographic bounding box definition for a city/region."""
    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

class CityPresets:
    """Static container for known city bounding boxes.

    Extend by calling ``CityPresets.register(City(...))`` early in your app
    before constructing a ``PipelineConfig`` that references the new name.
    """
    _PRESETS: Dict[str, City] = {
        "world": City("world", -90.0, 90.0, -180.0, 180.0),
        "germany": City("germany", 47.2, 55.1, 5.9, 15.2),
        "hamburg": City("hamburg", 53.3, 53.8, 9.6, 10.35),
        "berlin": City("berlin", 52.3, 52.7, 13.0, 13.8),
        "brussels": City("brussels", 50.8, 50.9, 4.3, 4.4),
        "zurich": City("zurich", 47.3, 47.4, 8.5, 8.6),
        "cologne": City("cologne", 50.82, 51.02, 6.75, 7.16),
        "munich": City("munich", 48.05, 48.25, 11.45, 11.65)
    }

    @staticmethod
    def get(name: str) -> City:
        key = name.lower()
        if key not in CityPresets._PRESETS:
            avail = ", ".join(sorted(CityPresets._PRESETS))
            raise ValueError(f"Unknown city '{name}'. Available: {avail}")
        return CityPresets._PRESETS[key]

    @staticmethod
    def list() -> Iterable[str]:
        return CityPresets._PRESETS.keys()

    @staticmethod
    def register(city: City, overwrite: bool = False) -> None:
        key = city.name.lower()
        if not overwrite and key in CityPresets._PRESETS:
            raise ValueError(f"City '{city.name}' already registered. Use overwrite=True to replace.")
        CityPresets._PRESETS[key] = city
