import { NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import { join } from 'path';
import { v4 as uuidv4 } from 'uuid';

export async function POST(request: Request) {
  try {
    const data = await request.formData();
    const file: File | null = data.get('file') as unknown as File;

    if (!file) {
      return NextResponse.json({ success: false, error: 'No file found in form data' }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const buffer = Buffer.from(bytes);

    // Extract the original extension from the file name
    const originalFilename = file.name || 'mockup.png';
    const extIndex = originalFilename.lastIndexOf('.');
    const ext = extIndex !== -1 ? originalFilename.slice(extIndex) : '.png';

    // Generate unique UUID filename
    const uniqueName = `${uuidv4()}${ext}`;

    const uploadDir = join(process.cwd(), 'public', 'uploads', 'mockups');

    try {
      // Attempt to create the directory if it doesn't exist
      await mkdir(uploadDir, { recursive: true });
    } catch (err: any) {
      if (err.code !== 'EEXIST') {
        throw err;
      }
    }

    const filePath = join(uploadDir, uniqueName);

    // Save physically to disk
    await writeFile(filePath, buffer);

    const publicUrl = `/uploads/mockups/${uniqueName}`;

    return NextResponse.json({ success: true, url: publicUrl });
  } catch (error: any) {
    console.error('Upload Error:', error);
    return NextResponse.json({ success: false, error: error.message || 'Internal server error' }, { status: 500 });
  }
}
