import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: Request) {
    try {
        const userId = request.headers.get('x-user-id');
        if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        // Upsert user to ensure they exist for mock auth purposes
        const user = await prisma.user.upsert({
            where: { id: userId },
            update: {},
            create: {
                id: userId,
                email: `${userId}@example.com`,
                tokens_balance: 5
            }
        });

        // Get total runs for this month
        const startOfMonth = new Date();
        startOfMonth.setDate(1);
        startOfMonth.setHours(0, 0, 0, 0);

        const totalRuns = await prisma.runHistory.count({
            where: {
                userId,
                createdAt: { gte: startOfMonth }
            }
        });

        return NextResponse.json({ ...user, totalRunsThisMonth: totalRuns });
    } catch (e: any) {
        return NextResponse.json({ error: 'Failed to fetch user stats' }, { status: 500 });
    }
}

export async function POST(request: Request) {
    try {
        const userId = request.headers.get('x-user-id');
        if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const body = await request.json();
        const { geminiApiKey } = body;

        const user = await prisma.user.upsert({
            where: { id: userId },
            update: { geminiApiKey },
            create: {
                id: userId,
                email: `${userId}@example.com`,
                tokens_balance: 5,
                geminiApiKey
            }
        });

        return NextResponse.json({ success: true });
    } catch (e: any) {
        return NextResponse.json({ error: 'Failed to update user' }, { status: 500 });
    }
}
