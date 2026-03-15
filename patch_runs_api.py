import sys

with open('app/api/runs/[workspaceId]/route.ts', 'r') as f:
    content = f.read()

replacement = '''export async function GET(
  request: Request,
  { params }: { params: Promise<{ workspaceId: string }> }
) {
  try {
    const { workspaceId } = await params;
    const userId = request.headers.get('x-user-id');
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId }
    });
    if (!workflow) return NextResponse.json([]);

    const runs = await prisma.runHistory.findMany({
      where: { workflowId: workflow.id, userId },
      orderBy: { createdAt: 'desc' },
      take: 20
    });
    return NextResponse.json(runs);'''

target = '''export async function GET(
  request: Request,
  { params }: { params: Promise<{ workspaceId: string }> }
) {
  try {
    const { workspaceId } = await params;

    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId }
    });
    if (!workflow) return NextResponse.json([]);

    const runs = await prisma.runHistory.findMany({
      where: { workflowId: workflow.id },
      orderBy: { createdAt: 'desc' },
      take: 20
    });
    return NextResponse.json(runs);'''

content = content.replace(target, replacement)

with open('app/api/runs/[workspaceId]/route.ts', 'w') as f:
    f.write(content)
