import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File;
    
    if (!file) {
      return NextResponse.json({ detail: "No file uploaded" }, { status: 400 });
    }

    // Simulate longer delay for upload processing
    await new Promise((resolve) => setTimeout(resolve, 1500));

    return NextResponse.json({
      file_id: Date.now().toString(),
      filename: file.name,
      size_bytes: file.size,
      type: file.type,
      uploaded_at: new Date().toISOString()
    });
  } catch (error) {
    return NextResponse.json({ detail: "Internal Server Error" }, { status: 500 });
  }
}
