import { NextResponse } from 'next/server';

export async function POST(request: Request) {
    try {
        const userId = request.headers.get('x-user-id');
        if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const body = await request.json();

        // Forward resume request to FastAPI backend
        const res = await fetch(`http://127.0.0.1:5000/resume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!res.ok) {
            const err = await res.json();
            return NextResponse.json({ error: err.error || 'Backend failed to resume' }, { status: res.status });
        }

        const data = await res.json();
        return NextResponse.json(data);
    } catch (e: any) {
        return NextResponse.json({ error: 'Failed to process resume' }, { status: 500 });
    }
}
