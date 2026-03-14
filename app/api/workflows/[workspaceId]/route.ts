import { NextResponse, NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest, { params }: { params: Promise<{ workspaceId: string }> }) {
  try {
    const { workspaceId } = await params;
    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId }
    });

    if (!workflow) {
      return NextResponse.json({ nodes: [], edges: [] });
    }

    return NextResponse.json({
      nodes: JSON.parse(workflow.nodes),
      edges: JSON.parse(workflow.edges)
    });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch workflow' }, { status: 500 });
  }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ workspaceId: string }> }) {
  try {
    const { workspaceId } = await params;
    const { nodes, edges } = await request.json();

    const workflow = await prisma.workflowBlueprint.upsert({
      where: { workspaceId },
      update: {
        nodes: JSON.stringify(nodes),
        edges: JSON.stringify(edges)
      },
      create: {
        workspaceId,
        nodes: JSON.stringify(nodes),
        edges: JSON.stringify(edges)
      }
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to save workflow' }, { status: 500 });
  }
}
