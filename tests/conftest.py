from __future__ import annotations

import os

import pytest

from spectrum_systems.modules.runtime.repo_write_lineage_guard import reset_repo_write_lineage_replay_state
from spectrum_systems.modules.runtime.lineage_issuance_registry import reset_lineage_issuance_registry_state


os.environ.setdefault("SPECTRUM_LINEAGE_AUTH_SECRET_AEX", "test-lineage-auth-secret-aex")
os.environ.setdefault("SPECTRUM_LINEAGE_AUTH_SECRET_TLC", "test-lineage-auth-secret-tlc")
os.environ.setdefault("SPECTRUM_LINEAGE_AUTH_KEY_ID_AEX", "aex-hs256-v1")
os.environ.setdefault("SPECTRUM_LINEAGE_AUTH_KEY_ID_TLC", "tlc-hs256-v1")
os.environ.setdefault("SPECTRUM_LINEAGE_AUTH_TTL_SECONDS", "900")
os.environ.setdefault("SPECTRUM_LINEAGE_AUTH_MAX_AGE_SECONDS", "3600")


@pytest.fixture(autouse=True)
def _reset_lineage_replay_state() -> None:
    reset_repo_write_lineage_replay_state()
    reset_lineage_issuance_registry_state(clear_persistent_registry=True)
