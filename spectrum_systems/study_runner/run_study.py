"""
CLI entrypoint for running a Spectrum Study Compiler analysis.

Usage:
    python -m spectrum_systems.study_runner.run_study study_config.yaml
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from spectrum_systems.modules.runtime.trace_engine import (
    SPAN_STATUS_ERROR,
    SPAN_STATUS_OK,
    end_span,
    start_span,
    start_trace,
)

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
    trace_id = start_trace({"component": "study_runner", "config_path": str(config.config_path)})
    span_id = start_span(trace_id, "study_runner.write_outputs")
    try:
        results = write_outputs(
            config,
            pipeline_outputs,
            logger,
            policy_id=_load_active_policy_id(),
            generated_by_version=_resolve_git_revision(),
            source_revision=_resolve_source_revision(config.config_path),
            trace_id=trace_id,
            span_id=span_id,
        )
        end_span(span_id, SPAN_STATUS_OK)
    except Exception:
        end_span(span_id, SPAN_STATUS_ERROR)
        raise
    logger.info(
        "Study run completed.",
        extra={
            "run_id": results["run_id"],
            "results_path": results["results_path"],
            "study_summary_path": results["study_summary_path"],
        },
    )
    return 0


def _resolve_git_revision() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    revision = proc.stdout.strip()
    if proc.returncode != 0 or not revision:
        raise RuntimeError("Unable to resolve repository revision via git rev-parse --short=12 HEAD")
    return revision


def _resolve_source_revision(config_path: Path) -> str:
    if not config_path.exists():
        raise RuntimeError(f"Cannot resolve source revision for missing config: {config_path}")
    return f"rev{config_path.stat().st_mtime_ns}"


def _load_active_policy_id() -> str:
    policy_path = Path("config") / "regression_policy.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    policy_id = str(payload.get("policy_id", "")).strip()
    if not policy_id:
        raise RuntimeError("config/regression_policy.json is missing required policy_id")
    return policy_id


if __name__ == "__main__":
    raise SystemExit(main())
