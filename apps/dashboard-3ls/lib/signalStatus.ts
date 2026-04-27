import type { DashboardSignal, DataSource, SignalStatus } from './types';
import { dataSourceAllowsHealthy } from './truthClassifier';

// DSH-04 / DSH-05: No green without source.
//
// Given a signal whose underlying logic produced a status, normalize that
// status against its declared data_source. The truth contract is:
//
//   artifact_store / repo_registry -> may render healthy if status is healthy
//   derived                        -> may render healthy ONLY IF every
//                                     declared source artifact is present
//   derived_estimate               -> may render warning at best (never green)
//   stub_fallback                  -> may render unknown at best (never green)
//   unknown                        -> renders unknown or critical
//
// This function is pure; it never invents a healthy result.

export interface NormalizeOptions {
  // For derived signals: the count of artifacts the signal required vs.
  // the count actually present. Used to enforce "all sources present"
  // before allowing a derived signal to render healthy.
  requiredArtifactCount?: number;
  loadedArtifactCount?: number;
}

export function normalizeSignalStatus<TValue>(
  signal: DashboardSignal<TValue>,
  options: NormalizeOptions = {}
): DashboardSignal<TValue> {
  const ds = signal.data_source;
  const incomingStatus = signal.status;
  const reasonCodes = new Set(signal.reason_codes);

  // unknown values are never healthy regardless of source.
  if (signal.value === 'unknown') {
    reasonCodes.add('value_unknown');
    return {
      ...signal,
      status: incomingStatus === 'critical' ? 'critical' : 'unknown',
      reason_codes: Array.from(reasonCodes),
    };
  }

  let status: SignalStatus = incomingStatus;

  switch (ds) {
    case 'artifact_store':
    case 'repo_registry':
      // Trust the upstream status; nothing to degrade.
      break;

    case 'derived': {
      const required = options.requiredArtifactCount ?? signal.source_artifacts_used.length;
      const loaded = options.loadedArtifactCount ?? signal.source_artifacts_used.length;
      if (loaded < required) {
        // Missing input: degrade to derived_estimate semantics.
        reasonCodes.add('derived_partial_inputs');
        if (status === 'healthy') status = 'warning';
      }
      break;
    }

    case 'derived_estimate': {
      reasonCodes.add('provisional_truth');
      if (status === 'healthy') status = 'warning';
      break;
    }

    case 'stub_fallback': {
      reasonCodes.add('stub_fallback_no_source');
      // Stubs cannot render healthy or warning-as-positive; cap at unknown.
      // If upstream says critical we preserve that — fail-closed beats unknown.
      if (status === 'healthy' || status === 'warning') status = 'unknown';
      break;
    }

    case 'unknown': {
      reasonCodes.add('source_unknown');
      if (status === 'healthy' || status === 'warning') status = 'unknown';
      break;
    }
  }

  // Final invariant: if data_source forbids healthy, healthy must not survive.
  if (status === 'healthy' && !dataSourceAllowsHealthy(ds)) {
    status = 'unknown';
    reasonCodes.add('healthy_blocked_by_source');
  }

  return {
    ...signal,
    status,
    reason_codes: Array.from(reasonCodes),
  };
}

// Map the legacy SystemCard status union to a DSH-04-safe status given a
// declared data_source. Used by the systems API to keep the existing card
// payload shape while honouring no-green-without-source.
export function safeCardStatus(
  status: SignalStatus,
  data_source: DataSource
): 'healthy' | 'warning' | 'critical' {
  // Dashboard card surface is intentionally strict: no "unknown" card status.
  // Unknown raw inputs must be degraded to warning/critical with fail-closed bias.
  if (status === 'unknown') {
    if (data_source === 'stub_fallback' || data_source === 'unknown') return 'critical';
    return 'warning';
  }

  if (status === 'healthy' && !dataSourceAllowsHealthy(data_source)) {
    return data_source === 'derived_estimate' ? 'warning' : 'critical';
  }
  return status;
}
