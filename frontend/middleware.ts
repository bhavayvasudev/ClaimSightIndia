import { auth } from "@/auth";
import { NextResponse } from "next/server";

// The Google sign-in gate applies to the whole real claim flow and the
// dashboard, not just the CTA button — otherwise it's just UI theater
// bypassable by typing the URL directly.
export default auth((req) => {
  if (!req.auth) {
    const signInUrl = new URL("/signin", req.nextUrl.origin);
    signInUrl.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return NextResponse.redirect(signInUrl);
  }
});

export const config = {
  matcher: ["/claims/:path*", "/dashboard/:path*", "/profile/:path*"],
};
