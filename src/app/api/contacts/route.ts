import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const contacts = await prisma.contact.findMany({
    orderBy: { createdAt: "desc" },
  });
  return NextResponse.json(contacts);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const name = String(body.name ?? "").trim();
  const email = String(body.email ?? "").trim().toLowerCase();
  const company = body.company ? String(body.company).trim() : null;
  const phone = body.phone ? String(body.phone).trim() : null;
  const status = body.status ? String(body.status).trim() : "lead";

  if (!name || !email) {
    return NextResponse.json(
      { error: "Name and email are required." },
      { status: 400 },
    );
  }

  const contact = await prisma.contact.create({
    data: { name, email, company, phone, status },
  });

  return NextResponse.json(contact, { status: 201 });
}
