"""
Deterministic study pipeline for the Spectrum Study Compiler.

Each pipeline stage is a pure function that accepts structured inputs,
produces intermediate artifacts, and can be inspected independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import hashlib
import logging
import math
import json

from .load_config import StudyConfig


@dataclass
class Deployment:
    system_name: str
    density_per_km2: float
    estimated_sites: int
    antenna_height_m: float


@dataclass
class PathLossResult:
    system_name: str
    model: str
    distance_km: float
    frequency_mhz: float
    median_pathloss_db: float


@dataclass
class InterferenceResult:
    system_name: str
    interference_dbm: float
    margin_to_threshold_db: float


@dataclass
class ProtectionZone:
    system_name: str
    radius_km: float
    status: str


def _log_event(logger: logging.Logger, event: str, **fields) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, sort_keys=True))


def generate_deployments(config: StudyConfig, logger: logging.Logger) -> List[Deployment]:
    base_density = config.deployment.base_station_density_per_km2
    deployments: List[Deployment] = []
    for idx, system in enumerate(config.systems, start=1):
        estimated_sites = max(1, int(round(base_density * 10 * (1 + idx * 0.05))))
        deployment = Deployment(
            system_name=system.name,
            density_per_km2=base_density,
            estimated_sites=estimated_sites,
            antenna_height_m=config.deployment.antenna_height_m,
        )
        _log_event(
            logger,
            "pipeline.deployment",
            system=system.name,
            density_per_km2=base_density,
            estimated_sites=estimated_sites,
        )
        deployments.append(deployment)
    return deployments


def compute_pathloss(
    config: StudyConfig, deployments: List[Deployment], logger: logging.Logger
) -> List[PathLossResult]:
    center_freq = (config.band.start_freq_mhz + config.band.end_freq_mhz) / 2.0
    # Fixed deterministic distance to avoid stochastic behavior.
    assumed_distance_km = 10.0
    results: List[PathLossResult] = []
    for deployment in deployments:
        median_pathloss_db = 32.45 + 20 * math.log10(center_freq) + 20 * math.log10(
            assumed_distance_km
        )
        result = PathLossResult(
            system_name=deployment.system_name,
            model=config.propagation_model.model,
            distance_km=assumed_distance_km,
            frequency_mhz=center_freq,
            median_pathloss_db=round(median_pathloss_db, 2),
        )
        _log_event(
            logger,
            "pipeline.pathloss",
            system=deployment.system_name,
            pathloss_db=result.median_pathloss_db,
            model=config.propagation_model.model,
        )
        results.append(result)
    return results


def compute_interference(
    config: StudyConfig, pathloss_results: List[PathLossResult], logger: logging.Logger
) -> List[InterferenceResult]:
    tx_power_dbm = 30.0  # Assumed e.i.r.p in dBm for deterministic computation.
    interference_results: List[InterferenceResult] = []
    for result in pathloss_results:
        received_power = tx_power_dbm - result.median_pathloss_db
        margin = config.protection_criteria.i_n_db - received_power
        interference = InterferenceResult(
            system_name=result.system_name,
            interference_dbm=round(received_power, 2),
            margin_to_threshold_db=round(margin, 2),
        )
        _log_event(
            logger,
            "pipeline.interference",
            system=result.system_name,
            interference_dbm=interference.interference_dbm,
            margin_db=interference.margin_to_threshold_db,
        )
        interference_results.append(interference)
    return interference_results


def evaluate_protection_criteria(
    config: StudyConfig, interference_results: List[InterferenceResult], logger: logging.Logger
) -> Dict[str, bool]:
    evaluations: Dict[str, bool] = {}
    for result in interference_results:
        meets_threshold = result.margin_to_threshold_db >= 0
        evaluations[result.system_name] = meets_threshold
        _log_event(
            logger,
            "pipeline.protection_eval",
            system=result.system_name,
            meets_threshold=meets_threshold,
            reliability_target=config.protection_criteria.reliability,
        )
    return evaluations


def determine_protection_zones(
    interference_results: List[InterferenceResult], logger: logging.Logger
) -> List[ProtectionZone]:
    zones: List[ProtectionZone] = []
    for result in interference_results:
        radius_km = max(5.0, 5.0 + max(0.0, -result.margin_to_threshold_db))
        status = "protected" if result.margin_to_threshold_db >= 0 else "mitigation-required"
        zone = ProtectionZone(
            system_name=result.system_name,
            radius_km=round(radius_km, 2),
            status=status,
        )
        _log_event(
            logger,
            "pipeline.protection_zone",
            system=result.system_name,
            radius_km=zone.radius_km,
            status=status,
        )
        zones.append(zone)
    return zones


def generate_tables(
    deployments: List[Deployment],
    pathloss_results: List[PathLossResult],
    interference_results: List[InterferenceResult],
    zones: List[ProtectionZone],
) -> Dict[str, List[dict]]:
    deployment_rows = [
        {
            "system": deployment.system_name,
            "density_per_km2": deployment.density_per_km2,
            "estimated_sites": deployment.estimated_sites,
            "antenna_height_m": deployment.antenna_height_m,
        }
        for deployment in deployments
    ]
    pathloss_rows = [
        {
            "system": result.system_name,
            "model": result.model,
            "distance_km": result.distance_km,
            "frequency_mhz": result.frequency_mhz,
            "median_pathloss_db": result.median_pathloss_db,
        }
        for result in pathloss_results
    ]
    interference_rows = [
        {
            "system": result.system_name,
            "interference_dbm": result.interference_dbm,
            "margin_to_threshold_db": result.margin_to_threshold_db,
        }
        for result in interference_results
    ]
    protection_rows = [
        {
            "system": zone.system_name,
            "radius_km": zone.radius_km,
            "status": zone.status,
        }
        for zone in zones
    ]
    return {
        "deployment_summary": deployment_rows,
        "pathloss_summary": pathloss_rows,
        "interference_summary": interference_rows,
        "protection_zones": protection_rows,
    }


def generate_figures_metadata(
    interference_results: List[InterferenceResult], zones: List[ProtectionZone]
) -> List[dict]:
    figures = []
    for result, zone in zip(interference_results, zones):
        figure_id = f"FIG-{hashlib.sha256(result.system_name.encode()).hexdigest()[:8]}"
        figures.append(
            {
                "artifact_id": figure_id,
                "artifact_type": "figure",
                "title": f"Interference profile for {result.system_name}",
                "description": (
                    "Deterministic interference projection with protection zone overlay."
                ),
                "metrics": ["interference_dbm", "margin_to_threshold_db"],
                "source_scenarios": [result.system_name],
                "render_ref": f"outputs/figures/{result.system_name.lower()}_interference.png",
                "provenance": {},
                "status": "draft",
            }
        )
    return figures


def run_pipeline(config: StudyConfig, logger: logging.Logger) -> dict:
    deployments = generate_deployments(config, logger)
    pathloss_results = compute_pathloss(config, deployments, logger)
    interference_results = compute_interference(config, pathloss_results, logger)
    evaluations = evaluate_protection_criteria(config, interference_results, logger)
    zones = determine_protection_zones(interference_results, logger)
    tables = generate_tables(deployments, pathloss_results, interference_results, zones)
    figures_metadata = generate_figures_metadata(interference_results, zones)

    return {
        "deployments": deployments,
        "pathloss": pathloss_results,
        "interference": interference_results,
        "protection_evaluations": evaluations,
        "protection_zones": zones,
        "tables": tables,
        "figures_metadata": figures_metadata,
    }
