import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    
    // Forward to real backend
    const response = await fetch(`${BACKEND_URL}/api/v1/agent/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: req.headers.get("authorization") || "",
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Agent API error:", error);
    return NextResponse.json({ detail: "Internal Server Error" }, { status: 500 });
  }
}
