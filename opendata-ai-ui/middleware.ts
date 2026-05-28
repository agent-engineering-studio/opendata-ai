import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Routes accessible to anonymous visitors. Everything else requires auth.
const isPublicRoute = createRouteMatcher([
  "/",                  // marketing landing (linkable from anywhere)
  "/sign-in(.*)",
  "/sign-up(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  // The Clerk quickstart matcher: skip Next.js internals + static files,
  // include every API path and Clerk's own auto-proxy path.
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
  ],
};
