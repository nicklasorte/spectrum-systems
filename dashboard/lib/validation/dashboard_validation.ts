import type { ArtifactRecord } from '../../types/dashboard'

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

function isString(v: unknown): v is string {
  return typeof v === 'string' && v.trim().length > 0
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((item) => typeof item === 'string')
}

function isNonEmptyStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.length > 0 && v.every((item) => typeof item === 'string' && item.trim().length > 0)
}

function isNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

function isIsoUtcTimestamp(v: unknown): v is string {
  return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(v.trim())
}

function requireField(data: Record<string, unknown>, field: string, check: (value: unknown) => boolean, message: string): string | null {
  if (!check(data[field])) return message
  return null
}

export function validateArtifactShape(name: string, data: unknown): { valid: boolean; error?: string } {
  if (data === null || data === undefined) return { valid: false, error: `${name} is null` }

  if (name === 'repo_snapshot_meta.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'data_source_state', (value) => value === 'live' || value === 'stale' || value === 'offline', `${name} invalid data_source_state enum`) ??
      requireField(data, 'last_refreshed_time', isString, `${name} missing last_refreshed_time string`)
    return err ? { valid: false, error: err } : { valid: true }
  }

  if (name === 'dashboard_freshness_status.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'status', (value) => value === 'fresh' || value === 'stale' || value === 'unknown', `${name} invalid status enum`) ??
      requireField(data, 'snapshot_last_refreshed_time', isIsoUtcTimestamp, `${name} missing/invalid snapshot_last_refreshed_time ISO UTC`) ??
      requireField(data, 'freshness_window_hours', isNumber, `${name} missing freshness_window_hours number`)
    return err ? { valid: false, error: err } : { valid: true }
  }

  if (name === 'dashboard_publication_manifest.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const validPublicationStates = ['live', 'stale', 'offline']
    const publicationStateErr = requireField(
      data,
      'publication_state',
      (value) => validPublicationStates.includes(String(value)),
      `${name} invalid publication_state enum`
    )
    if (publicationStateErr) return { valid: false, error: publicationStateErr }

    const artifactCountErr = requireField(data, 'artifact_count', isNumber, `${name} missing artifact_count number`)
    if (artifactCountErr) return { valid: false, error: artifactCountErr }

    const requiredFilesErr = requireField(
      data,
      'required_files',
      isNonEmptyStringArray,
      `${name} required_files must be non-empty string[]`
    )
    if (requiredFilesErr) return { valid: false, error: requiredFilesErr }

    const requiredFiles = data.required_files as string[]
    if (new Set(requiredFiles).size !== requiredFiles.length) {
      return { valid: false, error: `${name} required_files must contain unique entries` }
    }
    const artifactCount = data.artifact_count as number
    const allowsManifestSelfCount = requiredFiles.includes('dashboard_publication_manifest.json')
      ? requiredFiles.length + 1
      : requiredFiles.length

    if (artifactCount !== requiredFiles.length && artifactCount !== allowsManifestSelfCount) {
      return { valid: false, error: `${name} artifact_count must match required_files length (or +1 when manifest self-counted)` }
    }

    return { valid: true }
  }

  if (name === 'hard_gate_status_record.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const readinessStatus = data.readiness_status ?? data.pass_fail
    if (!['ready', 'pass', 'blocked', 'failed', 'fail', 'unknown'].includes(String(readinessStatus))) {
      return { valid: false, error: `${name} invalid readiness_status/pass_fail enum` }
    }
    return { valid: true }
  }

  if (name === 'current_run_state_record.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const runStatus = data.current_run_status ?? data.status
    if (!['healthy', 'ready', 'blocked', 'repair_required', 'failed', 'fail', 'completed', 'running', 'unknown'].includes(String(runStatus))) {
      return { valid: false, error: `${name} invalid current_run_status/status enum` }
    }
    if (data.repair_loop_count !== undefined && !isNumber(data.repair_loop_count)) {
      return { valid: false, error: `${name} repair_loop_count must be number when provided` }
    }
    return { valid: true }
  }

  if (name === 'next_action_recommendation_record.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    if (data.artifact_type !== 'next_action_recommendation_record_collection') {
      return { valid: false, error: `${name} invalid artifact_type` }
    }
    if (!Array.isArray(data.records) || data.records.length === 0) {
      return { valid: false, error: `${name} records must be non-empty array` }
    }
    for (const [idx, record] of data.records.entries()) {
      if (!isObject(record)) return { valid: false, error: `${name} records[${idx}] must be object` }
      if (record.artifact_type !== 'next_action_recommendation_record') {
        return { valid: false, error: `${name} records[${idx}] invalid artifact_type` }
      }
      if (!isString(record.recommended_next_action)) {
        return { valid: false, error: `${name} records[${idx}] missing recommended_next_action string` }
      }
      if (record.confidence !== undefined && !isNumber(record.confidence)) {
        return { valid: false, error: `${name} records[${idx}] confidence must be number when provided` }
      }
      if (record.source_basis !== undefined && !isStringArray(record.source_basis)) {
        return { valid: false, error: `${name} records[${idx}] source_basis must be string[] when provided` }
      }
      if (record.provenance_categories !== undefined && !isStringArray(record.provenance_categories)) {
        return { valid: false, error: `${name} records[${idx}] provenance_categories must be string[] when provided` }
      }
    }
    return { valid: true }
  }

  if (name === 'dashboard_publication_sync_audit.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'dashboard_publication_sync_audit', `${name} invalid artifact_type`) ??
      requireField(data, 'publication_state', isString, `${name} missing publication_state string`) ??
      requireField(data, 'published_at', isIsoUtcTimestamp, `${name} missing/invalid published_at ISO UTC`) ??
      requireField(data, 'required_artifact_count', isNumber, `${name} missing required_artifact_count number`) ??
      requireField(data, 'records', Array.isArray, `${name} missing records array`)
    if (err) return { valid: false, error: err }
    const records = data.records as unknown[]
    for (const [idx, row] of records.entries()) {
      if (!isObject(row)) return { valid: false, error: `${name} records[${idx}] must be object` }
      if (!isString(row.artifact) || !isString(row.source)) {
        return { valid: false, error: `${name} records[${idx}] missing artifact/source string` }
      }
    }
    return { valid: true }
  }

  if (name === 'refresh_run_record.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'refresh_run_record', `${name} invalid artifact_type`) ??
      requireField(data, 'refresh_run_id', isString, `${name} missing refresh_run_id string`) ??
      requireField(data, 'trace_id', isString, `${name} missing trace_id string`) ??
      requireField(data, 'trigger_mode', (value) => ['scheduled', 'manual', 'repair', 'test'].includes(String(value)), `${name} invalid trigger_mode`)
    return err ? { valid: false, error: err } : { valid: true }
  }

  if (name === 'publication_attempt_record.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'publication_attempt_record', `${name} invalid artifact_type`) ??
      requireField(data, 'trace_id', isString, `${name} missing trace_id string`) ??
      requireField(data, 'refresh_run_id', isString, `${name} missing refresh_run_id string`) ??
      requireField(data, 'decision', (value) => ['allow', 'block', 'freeze'].includes(String(value)), `${name} invalid decision enum`)
    return err ? { valid: false, error: err } : { valid: true }
  }


  if (name === 'judgment_application_artifact.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'judgment_application_artifact', `${name} invalid artifact_type`) ??
      requireField(data, 'decision_id', isString, `${name} missing decision_id string`) ??
      requireField(data, 'judgment_ids', isStringArray, `${name} missing judgment_ids string[]`)
    return err ? { valid: false, error: err } : { valid: true }
  }

  if (name === 'rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'operator_override_capture', `${name} invalid artifact_type`) ??
      requireField(data, 'overrides', Array.isArray, `${name} missing overrides array`)
    return err ? { valid: false, error: err } : { valid: true }
  }

  if (name === 'rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'recommendation_replay_pack', `${name} invalid artifact_type`) ??
      requireField(data, 'scenario_ids', isStringArray, `${name} missing scenario_ids string[]`)
    return err ? { valid: false, error: err } : { valid: true }
  }

  if (name === 'serial_bundle_validator_result.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'serial_bundle_validator_result', `${name} invalid artifact_type`) ??
      requireField(data, 'pass', (value) => typeof value === 'boolean', `${name} missing pass boolean`)
    return err ? { valid: false, error: err } : { valid: true }
  }

  if (name === 'dashboard_public_contract_coverage.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'dashboard_public_contract_coverage', `${name} invalid artifact_type`) ??
      requireField(data, 'covered_artifacts', isStringArray, `${name} missing covered_artifacts string[]`)
    return err ? { valid: false, error: err } : { valid: true }
  }

  if (name === 'governed_promotion_discipline_gate.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    const err = requireField(data, 'artifact_type', (value) => value === 'governed_promotion_discipline_gate', `${name} invalid artifact_type`) ??
      requireField(data, 'promotion_decision', isString, `${name} missing promotion_decision string`) ??
      requireField(data, 'allowed_decisions', isStringArray, `${name} missing allowed_decisions string[]`)
    return err ? { valid: false, error: err } : { valid: true }
  }
  if (name === 'deferred_item_register.json' || name === 'deferred_return_tracker.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    if (data.items !== undefined && !Array.isArray(data.items)) {
      return { valid: false, error: `${name} items must be array when provided` }
    }
    return { valid: true }
  }

  if (Array.isArray(data) || isObject(data)) {
    return { valid: true }
  }

  return { valid: false, error: `${name} must be JSON object or array` }
}

export function markValidated<T>(artifact: ArtifactRecord<T>): ArtifactRecord<T> {
  if (!artifact.exists) return artifact
  const check = validateArtifactShape(artifact.name, artifact.data)
  return {
    ...artifact,
    valid: check.valid,
    error: check.error ?? artifact.error
  }
}
