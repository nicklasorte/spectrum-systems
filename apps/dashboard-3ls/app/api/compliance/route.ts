export async function GET() {
  const systemsData = [
    { system_id: 'PQX', compliant: true, violations: [] },
    { system_id: 'RDX', compliant: false, violations: [{ rule: 'sequence_check', detail: 'Batch out of order' }] },
    { system_id: 'TPA', compliant: true, violations: [] },
    { system_id: 'MAP', compliant: true, violations: [] },
    { system_id: 'TLC', compliant: true, violations: [] },
    { system_id: 'RQX', compliant: true, violations: [] },
    { system_id: 'HNX', compliant: true, violations: [] },
    { system_id: 'GOV', compliant: true, violations: [] },
    { system_id: 'FRE', compliant: true, violations: [] },
    { system_id: 'RIL', compliant: true, violations: [] },
    { system_id: 'AEX', compliant: true, violations: [] },
    { system_id: 'DBB', compliant: true, violations: [] },
    { system_id: 'DEM', compliant: true, violations: [] },
    { system_id: 'MCL', compliant: true, violations: [] },
    { system_id: 'BRM', compliant: true, violations: [] },
    { system_id: 'XRL', compliant: false, violations: [{ rule: 'latency_sla', detail: 'P99 latency exceeded' }] },
    { system_id: 'NSX', compliant: true, violations: [] },
    { system_id: 'PRG', compliant: true, violations: [] },
    { system_id: 'RSM', compliant: true, violations: [] },
    { system_id: 'PRA', compliant: true, violations: [] },
    { system_id: 'LCE', compliant: false, violations: [{ rule: 'throughput', detail: 'Below baseline' }] },
    { system_id: 'ABX', compliant: true, violations: [] },
    { system_id: 'DCL', compliant: true, violations: [] },
    { system_id: 'SAL', compliant: true, violations: [] },
    { system_id: 'SAS', compliant: true, violations: [] },
    { system_id: 'SHA', compliant: true, violations: [] },
  ];

  const compliantCount = systemsData.filter(s => s.compliant).length;
  const violationCount = systemsData.filter(s => !s.compliant).length;

  return Response.json({
    status: 'success',
    total_systems: systemsData.length,
    compliant: compliantCount,
    violations: violationCount,
    by_system: systemsData,
    refreshed_at: new Date().toISOString(),
  });
}
