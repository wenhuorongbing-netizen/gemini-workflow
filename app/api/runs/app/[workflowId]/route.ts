import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(
    request: Request,
    { params }: { params: Promise<{ workflowId: string }> }
) {
    try {
        const { workflowId } = await params;
        const runs = await prisma.runHistory.findMany({
            where: { workflowId },
            orderBy: { createdAt: 'desc' },
            take: 5
        });
        return NextResponse.json(runs);
    } catch (error) {
        return NextResponse.json({ error: 'Failed to fetch app run history' }, { status: 500 });
    }
}
