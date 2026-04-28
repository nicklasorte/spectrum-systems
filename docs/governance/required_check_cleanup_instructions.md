# Required Check Cleanup Instructions (manual branch protection)

If branch protection is managed outside repo code:
1. In GitHub branch protection for `main`, set required status checks to canonical `pr-gate` check.
2. Remove stale required checks from retired workflows (`pytest`, `artifact-boundary` legacy jobs) once parity sign-off is complete.
3. Keep nightly deep gate non-blocking for PRs but required for release policy (if your org requires it).
4. Re-run `python scripts/run_required_check_alignment_audit.py` and archive output.
