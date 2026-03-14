"""
Configuration loader for the Spectrum Study Compiler runner.

Loads YAML study configuration files, validates required fields, and returns
structured dataclasses that downstream pipeline steps can consume in a
deterministic way.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union
import re


class ConfigError(Exception):
    """Raised when a configuration file cannot be loaded or validated."""


@dataclass
class BandConfig:
    start_freq_mhz: float
    end_freq_mhz: float

    def as_dict(self) -> dict:
        return {
            "start_freq_mhz": self.start_freq_mhz,
            "end_freq_mhz": self.end_freq_mhz,
        }


@dataclass
class SystemConfig:
    name: str
    system_type: str

    def as_dict(self) -> dict:
        return {"name": self.name, "type": self.system_type}


@dataclass
class PropagationModelConfig:
    model: str

    def as_dict(self) -> dict:
        return {"model": self.model}


@dataclass
class DeploymentConfig:
    base_station_density_per_km2: float
    antenna_height_m: float
    raw_density: str = field(repr=False)
    raw_height: str = field(repr=False)

    def as_dict(self) -> dict:
        return {
            "base_station_density_per_km2": self.base_station_density_per_km2,
            "antenna_height_m": self.antenna_height_m,
            "raw_density": self.raw_density,
            "raw_height": self.raw_height,
        }


@dataclass
class ProtectionCriteria:
    i_n_db: float
    reliability: float
    raw_i_n: str = field(repr=False)

    def as_dict(self) -> dict:
        return {
            "i_n_db": self.i_n_db,
            "reliability": self.reliability,
            "raw_i_n": self.raw_i_n,
        }


@dataclass
class StudyConfig:
    config_path: Path
    band: BandConfig
    systems: List[SystemConfig]
    propagation_model: PropagationModelConfig
    deployment: DeploymentConfig
    protection_criteria: ProtectionCriteria

    def as_dict(self) -> dict:
        return {
            "config_path": str(self.config_path),
            "band": self.band.as_dict(),
            "systems": [system.as_dict() for system in self.systems],
            "propagation_model": self.propagation_model.as_dict(),
            "deployment": self.deployment.as_dict(),
            "protection_criteria": self.protection_criteria.as_dict(),
        }


def _import_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - handled during runtime
        raise ConfigError(
            "PyYAML is required to load study configuration files. "
            "Install with `pip install pyyaml`."
        ) from exc
    return yaml


def _parse_float_with_unit(value: Union[str, float, int], field_name: str) -> float:
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"(-?\d+(?:\.\d+)?)", value)
        if match:
            return float(match.group(1))
    raise ConfigError(f"Field `{field_name}` must contain a numeric value, got {value!r}.")


def _parse_reliability(value: Union[str, float, int]) -> float:
    numeric = _parse_float_with_unit(value, "reliability")
    if numeric > 1:
        return numeric / 100.0
    if numeric <= 0:
        raise ConfigError("`reliability` must be greater than 0.")
    return numeric


def _validate_systems(systems: Optional[list]) -> List[SystemConfig]:
    if not systems or not isinstance(systems, list):
        raise ConfigError("`systems` must be a non-empty list.")
    parsed: List[SystemConfig] = []
    for entry in systems:
        if not isinstance(entry, dict):
            raise ConfigError("Each system entry must be a mapping with name and type.")
        name = entry.get("name")
        system_type = entry.get("type")
        if not name or not system_type:
            raise ConfigError("System entries require `name` and `type` fields.")
        parsed.append(SystemConfig(name=str(name), system_type=str(system_type)))
    return parsed


def _validate_band(band: Optional[dict]) -> BandConfig:
    if not isinstance(band, dict):
        raise ConfigError("`band` must be a mapping with `start_freq` and `end_freq`.")
    start = _parse_float_with_unit(band.get("start_freq"), "band.start_freq")
    end = _parse_float_with_unit(band.get("end_freq"), "band.end_freq")
    if start <= 0 or end <= 0:
        raise ConfigError("Band frequencies must be greater than zero.")
    if start >= end:
        raise ConfigError("`band.end_freq` must be greater than `band.start_freq`.")
    return BandConfig(start_freq_mhz=start, end_freq_mhz=end)


def _validate_propagation_model(model: Optional[dict]) -> PropagationModelConfig:
    if not isinstance(model, dict):
        raise ConfigError("`propagation_model` must be a mapping with `model`.")
    model_name = model.get("model")
    if not model_name:
        raise ConfigError("`propagation_model.model` is required.")
    return PropagationModelConfig(model=str(model_name))


def _validate_deployment(deployment: Optional[dict]) -> DeploymentConfig:
    if not isinstance(deployment, dict):
        raise ConfigError("`deployment` must be a mapping.")
    raw_density = deployment.get("base_station_density")
    raw_height = deployment.get("antenna_height")
    density = _parse_float_with_unit(raw_density, "deployment.base_station_density")
    height = _parse_float_with_unit(raw_height, "deployment.antenna_height")
    if density <= 0:
        raise ConfigError("`deployment.base_station_density` must be greater than zero.")
    if height <= 0:
        raise ConfigError("`deployment.antenna_height` must be greater than zero.")
    return DeploymentConfig(
        base_station_density_per_km2=density,
        antenna_height_m=height,
        raw_density=str(raw_density),
        raw_height=str(raw_height),
    )


def _validate_protection(protection: Optional[dict]) -> ProtectionCriteria:
    if not isinstance(protection, dict):
        raise ConfigError("`protection_criteria` must be a mapping.")
    raw_i_n = protection.get("I_N")
    reliability_raw = protection.get("reliability")
    i_n_db = _parse_float_with_unit(raw_i_n, "protection_criteria.I_N")
    reliability = _parse_reliability(reliability_raw)
    if reliability > 1:
        raise ConfigError("`protection_criteria.reliability` must be <= 1 (or <= 100%).")
    return ProtectionCriteria(i_n_db=i_n_db, reliability=reliability, raw_i_n=str(raw_i_n))


def load_config(config_path: Union[str, Path]) -> StudyConfig:
    """
    Load and validate a study configuration YAML file.

    Returns a `StudyConfig` dataclass with parsed numeric fields while preserving
    the original string representations for traceability.
    """
    yaml = _import_yaml()
    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ConfigError("Configuration root must be a mapping.")

    band = _validate_band(data.get("band"))
    systems = _validate_systems(data.get("systems"))
    propagation_model = _validate_propagation_model(data.get("propagation_model"))
    deployment = _validate_deployment(data.get("deployment"))
    protection_criteria = _validate_protection(data.get("protection_criteria"))

    return StudyConfig(
        config_path=path,
        band=band,
        systems=systems,
        propagation_model=propagation_model,
        deployment=deployment,
        protection_criteria=protection_criteria,
    )
