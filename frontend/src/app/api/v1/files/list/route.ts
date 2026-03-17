import { NextResponse } from "next/server";

export async function GET() {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Return some dummy files
  return NextResponse.json([
    {
      file_id: "0",
      filename: "titanic.csv",
      size_bytes: 61194,
      type: "text/csv",
      uploaded_at: new Date().toISOString()
    },
    {
      file_id: "1",
      filename: "financial_report_Q1.pdf",
      size_bytes: 2500000,
      type: "application/pdf",
      uploaded_at: new Date(Date.now() - 10000000).toISOString()
    },
    {
      file_id: "2",
      filename: "customer_churn_data.csv",
      size_bytes: 12000000,
      type: "text/csv",
      uploaded_at: new Date(Date.now() - 50000000).toISOString()
    }
  ]);
}
