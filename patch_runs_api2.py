import sys

with open('app/api/runs/[workflowId]/route.ts', 'r') as f:
    content = f.read()

replacement_get = '''export async function GET(request: NextRequest, { params }: { params: Promise<{ workflowId: string }> }) {
  try {
    const { workflowId } = await params;
    const userId = request.headers.get('x-user-id');
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    // Find the workflow blueprint ID since the param might be workspaceId depending on frontend mapping
    // We assume the frontend passes the `workspaceId` and we need to fetch its workflow runs
    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId: workflowId }
    });

    if (!workflow) {
      return NextResponse.json([]);
    }

    const runs = await prisma.runHistory.findMany({
      where: { workflowId: workflow.id, userId },
      orderBy: { createdAt: 'desc' }
    });

    return NextResponse.json(runs);'''

target_get = '''export async function GET(request: NextRequest, { params }: { params: Promise<{ workflowId: string }> }) {
  try {
    const { workflowId } = await params;

    // Find the workflow blueprint ID since the param might be workspaceId depending on frontend mapping
    // We assume the frontend passes the `workspaceId` and we need to fetch its workflow runs
    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId: workflowId }
    });

    if (!workflow) {
      return NextResponse.json([]);
    }

    const runs = await prisma.runHistory.findMany({
      where: { workflowId: workflow.id },
      orderBy: { createdAt: 'desc' }
    });

    return NextResponse.json(runs);'''


replacement_post = '''export async function POST(request: NextRequest, { params }: { params: Promise<{ workflowId: string }> }) {
  try {
    const { workflowId } = await params;
    const userId = request.headers.get('x-user-id');
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const { status, logs, results, nodes, edges } = await request.json();

    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId: workflowId }
    });

    if (!workflow) {
       return NextResponse.json({ error: 'Workflow blueprint not found. Save it first.' }, { status: 404 });
    }

    const run = await prisma.runHistory.create({
      data: {
        workflowId: workflow.id,
        userId,
        status,
        logs: JSON.stringify(logs),
        results: JSON.stringify(results),
        nodes: nodes ? JSON.stringify(nodes) : null,
        edges: edges ? JSON.stringify(edges) : null
      }
    });'''

target_post = '''export async function POST(request: NextRequest, { params }: { params: Promise<{ workflowId: string }> }) {
  try {
    const { workflowId } = await params;
    const { status, logs, results, nodes, edges } = await request.json();

    const workflow = await prisma.workflowBlueprint.findUnique({
      where: { workspaceId: workflowId }
    });

    if (!workflow) {
       return NextResponse.json({ error: 'Workflow blueprint not found. Save it first.' }, { status: 404 });
    }

    const run = await prisma.runHistory.create({
      data: {
        workflowId: workflow.id,
        status,
        logs: JSON.stringify(logs),
        results: JSON.stringify(results),
        nodes: nodes ? JSON.stringify(nodes) : null,
        edges: edges ? JSON.stringify(edges) : null
      }
    });'''

content = content.replace(target_get, replacement_get)
content = content.replace(target_post, replacement_post)

with open('app/api/runs/[workflowId]/route.ts', 'w') as f:
    f.write(content)
