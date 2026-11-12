import { authkitProxy } from "@workos-inc/authkit-nextjs";

export default authkitProxy();

export const config = {
  matcher: ["/workspaces/:path*", "/dashboard/:path*", "/onboarding/:path*", "/agents/:path*", "/test/:path*", "/knowledge/:path*", "/channels/:path*", "/conversations/:path*", "/developers/:path*", "/operations/:path*", "/settings/:path*", "/admin/:path*"],
};
