"""Governance modules for deterministic promotion/certification gates."""

from .done_certification import DoneCertificationError, run_done_certification

__all__ = ["DoneCertificationError", "run_done_certification"]
