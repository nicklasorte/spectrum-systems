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
      requireField(data, 'snapshot_last_refreshed_time', isString, `${name} missing snapshot_last_refreshed_time string`) ??
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
