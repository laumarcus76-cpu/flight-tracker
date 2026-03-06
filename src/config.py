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
    scan_months_ahead: int
    min_price_sanity: float = 10.0
    trip_patterns: list[list[str]] = field(
        default_factory=lambda: [["Friday", "Sunday"], ["Friday", "Monday"]]
    )


_REQUIRED = ["routes", "price_threshold", "scan_months_ahead"]


def load_config(path: str = "config.yaml") -> Config:
    """
    Load and validate config from a YAML file.

    Args:
        path: path to the config YAML file

    Returns:
        Validated Config dataclass instance.

    Raises:
        FileNotFoundError: if the config file does not exist
        ValueError: if required fields are missing or malformed
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{path} is empty or not valid YAML.")

    for key in _REQUIRED:
        if key not in data:
            raise ValueError(
                f"Missing required field '{key}' in {path}. "
                f"See config.example.yaml for the full schema."
            )

    raw_routes = data["routes"]
    if not isinstance(raw_routes, list) or len(raw_routes) == 0:
        raise ValueError("'routes' must be a non-empty list in config.yaml.")

    routes = []
    for i, r in enumerate(raw_routes):
        if not isinstance(r, dict) or "origin" not in r or "destination" not in r:
            raise ValueError(
                f"Route #{i + 1} must have 'origin' and 'destination' fields."
            )
        routes.append(Route(origin=str(r["origin"]), destination=str(r["destination"])))

    threshold = float(data["price_threshold"])
    scan_months = int(data["scan_months_ahead"])

    if threshold <= 0:
        raise ValueError("'price_threshold' must be a positive number.")
    if scan_months < 1:
        raise ValueError("'scan_months_ahead' must be at least 1.")

    trip_patterns = data.get(
        "trip_patterns", [["Friday", "Sunday"], ["Friday", "Monday"]]
    )
    min_price_sanity = float(data.get("min_price_sanity", 10.0))

    return Config(
        routes=routes,
        price_threshold=threshold,
        scan_months_ahead=scan_months,
        min_price_sanity=min_price_sanity,
        trip_patterns=trip_patterns,
    )
