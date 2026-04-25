// Incident data is statically defined stub data; no artifact source exists.
// All responses are labeled stub_fallback so consumers know these are not
// live incident signals.

export async function GET() {
  const incidents = [
    {
      id: 'INC001',
      system_id: 'RDX',
      title: 'Batch out of sequence',
      severity: 'warning' as const,
      duration: '2 hours',
      status: 'open' as const,
      root_cause: 'Batch processing order violation',
      recommended_fix: 'Verify sequencing checkpoint and restart batch',
      runbook_url: '/runbooks/batch-sequencing',
    },
    {
      id: 'INC002',
      system_id: 'XRL',
      title: 'P99 latency exceeded',
      severity: 'critical' as const,
      duration: '4 hours',
      status: 'investigating' as const,
      root_cause: 'External API timeout in reality loop',
      recommended_fix: 'Increase timeout threshold and retry logic',
      runbook_url: '/runbooks/latency-troubleshooting',
    },
    {
      id: 'INC003',
      system_id: 'FRE',
      title: 'Repair loop detected',
      severity: 'warning' as const,
      duration: '30 minutes',
      status: 'resolved' as const,
      root_cause: 'Self-healing triggered by false positive',
      recommended_fix: 'Review alarm thresholds',
      runbook_url: '/runbooks/false-positives',
    },
    {
      id: 'INC004',
      system_id: 'AEX',
      title: 'Admission queue backlog',
      severity: 'warning' as const,
      duration: '1 hour',
      status: 'investigating' as const,
      root_cause: 'Spike in admission requests',
      recommended_fix: 'Scale admission handlers',
      runbook_url: '/runbooks/queue-backlog',
    },
  ];

  return Response.json({
    status: 'success',
    data_source: 'stub_fallback',
    generated_at: new Date().toISOString(),
    source_artifacts_used: [],
    warnings: [
      'Incident data is statically defined; no artifact source exists. These are not live incident signals.',
    ],
    incidents,
    total: incidents.length,
    refreshed_at: new Date().toISOString(),
  });
}
