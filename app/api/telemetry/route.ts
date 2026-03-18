import { NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export async function POST(req: Request) {
  try {
    const data = await req.json();
    const { runId, agentRole, tokensPrompt, tokensCompletion, costEstimated } = data;

    if (!runId || !agentRole) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }

    const log = await prisma.telemetryLog.create({
      data: {
        runId,
        agentRole,
        tokensPrompt: Number(tokensPrompt) || 0,
        tokensCompletion: Number(tokensCompletion) || 0,
        costEstimated: Number(costEstimated) || 0,
      },
    });

    return NextResponse.json({ success: true, log });
  } catch (error) {
    console.error('Telemetry Error:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

export async function GET() {
  try {
    const logs = await prisma.telemetryLog.findMany({
      orderBy: { createdAt: 'desc' },
    });
    return NextResponse.json({ success: true, logs });
  } catch (error) {
    console.error('Telemetry Error:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
