import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = process.env.ADMIN_UI_COOKIE_NAME || "glink_admin_ui_session";
const PUBLIC_PATHS = ["/login"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }
  // Presence-only check — admin-api validates the JWT signature on every
  // request, so a forged cookie that survives this middleware just gets a
  // 401 from the API. This middleware only saves the round-trip when there
  // is no cookie at all.
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    const url = new URL("/login", req.url);
    if (pathname !== "/") url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/.*).*)"],
};
