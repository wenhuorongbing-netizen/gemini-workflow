import { NextResponse } from 'next/server';

export async function POST(request: Request) {
    try {
        const { searchParams } = new URL(request.url);
        const profile_id = searchParams.get('profile_id') || '1';

        // Proxy to the FastAPI backend running on port 5000
        const res = await fetch(`http://127.0.0.1:5000/api/accounts/login?profile_id=${profile_id}`, {
            method: 'POST'
        });

        const data = await res.json();
        return NextResponse.json(data);
    } catch (e: any) {
        return NextResponse.json({ status: 'error', message: e.message }, { status: 500 });
    }
}
