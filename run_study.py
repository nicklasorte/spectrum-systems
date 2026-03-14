"""
Wrapper script to run the Spectrum Study Compiler pipeline.

Usage:
    python run_study.py study_config.yaml
"""
from spectrum_systems.study_runner.run_study import main

if __name__ == "__main__":
    raise SystemExit(main())

