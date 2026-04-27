import { NextResponse } from 'next/server';
import { buildSystemGraphPayload } from '@/lib/systemGraphBuilder';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json(buildSystemGraphPayload(), { status: 200 });
}
