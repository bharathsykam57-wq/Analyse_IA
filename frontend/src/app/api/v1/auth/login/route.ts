import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 800));

    if (!body.email || !body.password) {
      return NextResponse.json({ detail: "Email and password required" }, { status: 400 });
    }

    // Mock successful login
    return NextResponse.json({
      access_token: "mock_access_token_123",
      refresh_token: "mock_refresh_token_456"
    });
  } catch (error) {
    return NextResponse.json({ detail: "Internal Server Error" }, { status: 500 });
  }
}
