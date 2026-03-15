import sys

with open('app/api/workspaces/route.ts', 'r') as f:
    content = f.read()

replacement_get = '''export async function GET(request: Request) {
  try {
    const userId = request.headers.get('x-user-id');
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const workspaces = await prisma.workspace.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      include: { workflows: true }
    });
    return NextResponse.json(workspaces);'''

target_get = '''export async function GET() {
  try {
    const workspaces = await prisma.workspace.findMany({
      orderBy: { createdAt: 'desc' },
      include: { workflows: true }
    });
    return NextResponse.json(workspaces);'''


replacement_post = '''export async function POST(request: Request) {
  try {
    const userId = request.headers.get('x-user-id');
    if (!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const { name } = await request.json();
    if (!name) {
      return NextResponse.json({ error: 'Name is required' }, { status: 400 });
    }

    const workspace = await prisma.workspace.create({
      data: { name, userId },
    });'''

target_post = '''export async function POST(request: Request) {
  try {
    const { name } = await request.json();
    if (!name) {
      return NextResponse.json({ error: 'Name is required' }, { status: 400 });
    }

    const workspace = await prisma.workspace.create({
      data: { name },
    });'''

content = content.replace(target_get, replacement_get)
content = content.replace(target_post, replacement_post)

with open('app/api/workspaces/route.ts', 'w') as f:
    f.write(content)
