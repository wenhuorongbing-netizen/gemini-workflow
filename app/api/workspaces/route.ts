import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET() {
  try {
    const workspaces = await prisma.workspace.findMany({
      orderBy: { createdAt: 'desc' },
      include: { workflows: true }
    });
    return NextResponse.json(workspaces);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch workspaces' }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { name } = await request.json();
    if (!name) {
      return NextResponse.json({ error: 'Name is required' }, { status: 400 });
    }

    const workspace = await prisma.workspace.create({
      data: { name },
    });

    return NextResponse.json(workspace);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to create workspace' }, { status: 500 });
  }
}
