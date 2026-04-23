export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const systemId = searchParams.get('system_id') || 'PQX';

  const generateTrendData = (base: number) => {
    const data = [];
    const today = new Date();
    for (let i = 6; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const variance = Math.sin(i * 0.5) * 5;
      data.push({
        date: date.toISOString().split('T')[0],
        health_score: Math.max(0, Math.min(100, base + variance + (Math.random() - 0.5) * 2)),
      });
    }
    return data;
  };

  const trends: Record<string, Array<{ date: string; health_score: number }>> = {
    PQX: generateTrendData(92),
    RDX: generateTrendData(88),
    TPA: generateTrendData(95),
    MAP: generateTrendData(90),
    TLC: generateTrendData(91),
    RQX: generateTrendData(87),
    HNX: generateTrendData(93),
    GOV: generateTrendData(96),
    FRE: generateTrendData(85),
    RIL: generateTrendData(89),
    AEX: generateTrendData(88),
    DBB: generateTrendData(94),
    DEM: generateTrendData(86),
    MCL: generateTrendData(90),
    BRM: generateTrendData(92),
    XRL: generateTrendData(80),
    NSX: generateTrendData(89),
    PRG: generateTrendData(91),
    RSM: generateTrendData(87),
    PRA: generateTrendData(84),
    LCE: generateTrendData(75),
    ABX: generateTrendData(88),
    DCL: generateTrendData(92),
    SAL: generateTrendData(95),
    SAS: generateTrendData(86),
    SHA: generateTrendData(89),
  };

  return Response.json({
    status: 'success',
    system_id: systemId,
    data: trends[systemId as keyof typeof trends] || trends.PQX,
    refreshed_at: new Date().toISOString(),
  });
}
