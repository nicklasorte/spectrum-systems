import { NextRequest, NextResponse } from 'next/server';

export async function GET(_req: NextRequest) {
  try {
    const proposals = [
      {
        proposal_id: 'PROP-001',
        phase_id: 'P1',
        phase_name: 'Wire EVL eval gate for RGE phases',
        failure_prevented: 'Phases promoted without eval coverage',
        signal_improved: 'eval_coverage_rate increases from 62% toward 90%',
        loop_leg: 'EVL',
        status: 'awaiting_cde',
        created_at: new Date().toISOString(),
        cde_decision_deadline: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
      },
    ];

    return NextResponse.json(proposals);
  } catch (error) {
    console.error('Error fetching proposals:', error);
    return NextResponse.json({ error: 'Failed to fetch proposals' }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { proposal_id, decision } = body;

    if (!proposal_id || !decision) {
      return NextResponse.json(
        { error: 'Missing proposal_id or decision' },
        { status: 400 }
      );
    }

    return NextResponse.json({
      result: 'decision_recorded',
      proposal_id,
      decision,
      recorded_at: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Error recording proposal decision:', error);
    return NextResponse.json({ error: 'Failed to record decision' }, { status: 500 });
  }
}
