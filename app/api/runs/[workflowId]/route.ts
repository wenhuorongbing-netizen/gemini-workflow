import { NextResponse, NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest, { params }: { params: Promise<{ workflowId: string }> }) {
  try {
    const { workflowId } = await params;
    const userId = request.headers.get('x-user-id');
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    // Find the workflow blueprint ID since the param might be workspaceId depending on frontend mapping
    // We assume the frontend passes the `workspaceId` and we need to fetch its workflow runs
    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId: workflowId }
    });

    if (!workflow) {
      return NextResponse.json([]);
    }

    const runs = await prisma.runHistory.findMany({
      where: { workflowId: workflow.id, userId },
      orderBy: { createdAt: 'desc' }
    });

    return NextResponse.json(runs);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch runs' }, { status: 500 });
  }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ workflowId: string }> }) {
  try {
    const { workflowId } = await params;
    const userId = request.headers.get('x-user-id');
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const { status, logs, results, nodes, edges } = await request.json();

    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId: workflowId }
    });

    if (!workflow) {
       return NextResponse.json({ error: 'Workflow blueprint not found. Save it first.' }, { status: 404 });
    }

    const run = await prisma.runHistory.create({
      data: {
        workflowId: workflow.id,
        userId,
        status,
        logs: JSON.stringify(logs),
        results: JSON.stringify(results),
        nodes: nodes ? JSON.stringify(nodes) : null,
        edges: edges ? JSON.stringify(edges) : null
      }
    });

    return NextResponse.json({ success: true, runId: run.id });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to save run history' }, { status: 500 });
  }
}
