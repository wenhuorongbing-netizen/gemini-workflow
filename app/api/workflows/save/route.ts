import { NextResponse, NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function POST(request: NextRequest) {
  try {
    const { workspaceId, nodes, edges } = await request.json();

    const triggerNodes = nodes.filter((n: any) => n.type === 'trigger' && n.data?.triggerType === 'cron');

    await prisma.workflowBlueprint.upsert({
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

    if (triggerNodes.length > 0) {
      try {
        const cronExpr = triggerNodes[0].data.cron || '0 0 * * *';
        fetch('http://127.0.0.1:5000/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            nodes,
            edges,
            is_cron: true,
            cron_expression: cronExpr
          })
        }).catch(err => console.error("Failed to sync cron to backend:", err));
      } catch (err) {
        console.error("Failed to sync cron to backend:", err);
      }
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ error: 'Failed to save workflow' }, { status: 500 });
  }
}
