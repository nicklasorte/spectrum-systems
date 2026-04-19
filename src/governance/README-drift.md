# Drift Detection

Monitors six entropy vectors:

1. **Decision Entropy**: Divergence in outcomes for same context
2. **Silent Drift**: Eval metrics shift gradually without triggering alerts
3. **Exception Accumulation**: Overrides pile up without conversion to policy
4. **Hidden Logic Creep**: New ungated decision paths appear
5. **Evaluation Blind Spots**: Slices with thin coverage
6. **Loss of Causality**: Trace IDs missing

Each detected drift produces a DriftSignal artifact with recommendations and can be marked resolved.
