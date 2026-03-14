"""
CLI entrypoint for running a Spectrum Study Compiler analysis.

Usage:
    python -m spectrum_systems.study_runner.run_study study_config.yaml
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .artifact_writer import write_outputs
from .load_config import ConfigError, load_config
from .pipeline import run_pipeline


def configure_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("study_runner")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a deterministic Spectrum Study Compiler pipeline."
    )
    parser.add_argument(
        "config_path",
        type=str,
        help="Path to the study configuration YAML file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger = configure_logging(Path("logs") / "study_run.log")

    try:
        config = load_config(args.config_path)
    except ConfigError as exc:
        logger.error(f"Configuration error: {exc}")
        return 1

    logger.info("Starting pipeline execution.")
    pipeline_outputs = run_pipeline(config, logger)
    logger.info("Pipeline execution finished, writing artifacts.")
    results = write_outputs(config, pipeline_outputs, logger)
    logger.info(
        "Study run completed.",
        extra={
            "run_id": results["run_id"],
            "results_path": results["results_path"],
            "study_summary_path": results["study_summary_path"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

