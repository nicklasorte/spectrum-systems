// Trend data is synthetically generated from a deterministic sine curve with
// no real telemetry artifact backing it. Every response is labeled stub_fallback
// so consumers know this data cannot support health claims.

const BASE_SCORES: Record<string, number> = {
  PQX: 92, RDX: 88, TPA: 95, MAP: 90, TLC: 91, RQX: 87, HNX: 93, GOV: 96,
  FRE: 85, RIL: 89, AEX: 88, DBB: 94, DEM: 86, MCL: 90, BRM: 92, XRL: 80,
  NSX: 89, PRG: 91, RSM: 87, PRA: 84, LCE: 75, ABX: 88, DCL: 92, SAL: 95,
  SAS: 86, SHA: 89,
};

function generateTrendData(base: number): Array<{ date: string; health_score: number }> {
  const data = [];
  const today = new Date();
  for (let i = 6; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    // Deterministic sine-only variance — stable across requests, no randomness.
    const variance = Math.sin(i * 0.5) * 5;
    data.push({
      date: date.toISOString().split('T')[0],
      health_score: Math.max(0, Math.min(100, Math.round((base + variance) * 10) / 10)),
    });
  }
  return data;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const systemId = searchParams.get('system_id') || 'PQX';
  const base = BASE_SCORES[systemId] ?? BASE_SCORES.PQX;

  return Response.json({
    status: 'success',
    data_source: 'stub_fallback',
    generated_at: new Date().toISOString(),
    source_artifacts_used: [],
    warnings: [
      'Trend data is synthetically generated; no telemetry artifact exists. These are not measured values and cannot support health claims.',
    ],
    system_id: systemId,
    data: generateTrendData(base),
    refreshed_at: new Date().toISOString(),
  });
}
