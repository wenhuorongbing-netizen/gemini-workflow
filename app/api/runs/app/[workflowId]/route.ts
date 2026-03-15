import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(
    request: Request,
    { params }: { params: Promise<{ workflowId: string }> }
) {
    try {
        const { workflowId } = await params;
        const userId = request.headers.get('x-user-id');
        if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const runs = await prisma.runHistory.findMany({
            where: { workflowId, userId },
            orderBy: { createdAt: 'desc' },
            take: 5
        });
        return NextResponse.json(runs);
    } catch (error) {
        return NextResponse.json({ error: 'Failed to fetch app run history' }, { status: 500 });
    }
}
