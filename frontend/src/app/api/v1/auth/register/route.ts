import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 1000));

    if (!body.email || !body.password || !body.full_name) {
      return NextResponse.json({ detail: "Missing fields" }, { status: 400 });
    }

    // Mock successful registration
    return NextResponse.json({
      id: "mock_user_1",
      email: body.email,
      full_name: body.full_name
    });
  } catch (error) {
    return NextResponse.json({ detail: "Internal Server Error" }, { status: 500 });
  }
}
