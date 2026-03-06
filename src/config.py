"""
Configuration loader.

Loads and validates config.yaml. Raises ValueError with a descriptive message
if required fields are missing or malformed.
"""

from dataclasses import dataclass, field

import yaml


@dataclass
class Route:
    origin: str
    destination: str


@dataclass
class Config:
    routes: list[Route]
    price_threshold: float
    departure_months: list[str]
    min_price_sanity: float = 10.0
    trip_length_min_days: int = 2
    trip_length_max_days: int = 7


def load_config(path: str = "config.yaml") -> Config:
    """
    Load and validate config from a YAML file.

    Args:
        path: path to the config YAML file

    Returns:
        Validated Config dataclass instance.

    Raises:
        ValueError: if required fields are missing or malformed
        FileNotFoundError: if the config file does not exist
    """
    raise NotImplementedError
