import { NextResponse, NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ task_id: string }> }
) {
  try {
    // Await the params to support Next.js 16+ async params
    const resolvedParams = await params;
    const taskId = resolvedParams.task_id;

    // Forward to real backend
    const response = await fetch(`${BACKEND_URL}/api/v1/agent/status/${taskId}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: req.headers.get("authorization") || "",
      },
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Agent status API error:", error);
    return NextResponse.json(
      { detail: "Internal Server Error" },
      { status: 500 }
    );
  }
}
