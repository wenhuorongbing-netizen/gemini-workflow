import sys

with open('app/api/runs/app/[workflowId]/route.ts', 'r') as f:
    content = f.read()

replacement = '''export async function GET(
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
        return NextResponse.json(runs);'''

target = '''export async function GET(
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
        return NextResponse.json(runs);'''

content = content.replace(target, replacement)

with open('app/api/runs/app/[workflowId]/route.ts', 'w') as f:
    f.write(content)
