"""Harness-evolution substrate (docs/TODO.md §12)."""

from harness.fingerprint import (
    INFRA_ABORT_KINDS,
    PASS1_FAILURE_STATUSES,
    classify_infra_abort,
    compute_harness_fingerprint,
    create_rollout,
    failure_mode_mix,
    finalize_rollout,
    latest_rollout,
)

__all__ = [
    "INFRA_ABORT_KINDS",
    "PASS1_FAILURE_STATUSES",
    "classify_infra_abort",
    "compute_harness_fingerprint",
    "create_rollout",
    "failure_mode_mix",
    "finalize_rollout",
    "latest_rollout",
]
