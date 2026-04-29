import { clerkMiddleware, createRouteMatcher, clerkClient } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// /cockpit/** requires an active session AND publicMetadata.role === "admin"
const isAdminRoute = createRouteMatcher(["/cockpit(.*)"]);

// /api/** requires only an active session (role check happens in FastAPI)
const isApiRoute = createRouteMatcher(["/api/(.*)"]);

export default clerkMiddleware(async (auth, req) => {
  if (isApiRoute(req)) {
    await auth.protect();
    return;
  }

  if (isAdminRoute(req)) {
    const { userId } = await auth();

    if (!userId) {
      return NextResponse.redirect(new URL("/?bloqueado=sem_login", req.url));
    }

    const client = await clerkClient();
    const user = await client.users.getUser(userId);

    if (user.publicMetadata.role !== "admin") {
      return NextResponse.redirect(new URL("/?bloqueado=sem_permissao", req.url));
    }
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
