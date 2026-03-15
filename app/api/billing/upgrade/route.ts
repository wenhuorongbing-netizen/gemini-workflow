import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function POST(request: Request) {
    try {
        const userId = request.headers.get('x-user-id');
        if (!userId) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        // Add 500 tokens
        const user = await prisma.user.upsert({
            where: { id: userId },
            update: {
                tokens_balance: { increment: 500 }
            },
            create: {
                id: userId,
                email: `${userId}@example.com`,
                tokens_balance: 505
            }
        });

        return NextResponse.json({ success: true, balance: user.tokens_balance });
    } catch (e: any) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
