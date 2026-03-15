import { NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export async function POST(
  request: Request,
  { params }: { params: Promise<{ workspaceId: string }> }
) {
  try {
    const { workspaceId } = await params;
    const { isPublished, publishedInputs } = await request.json();

    const workflow = await prisma.workflowBlueprint.update({
      where: { id: workspaceId },
      data: {
        isPublished: isPublished,
        publishedInputs: JSON.stringify(publishedInputs),
      },
    });

    return NextResponse.json(workflow);
  } catch (error: any) {
    console.error("Error publishing workflow:", error);
    return NextResponse.json(
      { error: "Failed to publish workflow", details: error.message },
      { status: 500 }
    );
  }
}
