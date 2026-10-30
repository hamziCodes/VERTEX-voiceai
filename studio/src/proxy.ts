import { authkitProxy } from "@workos-inc/authkit-nextjs";

export default authkitProxy();

export const config = {
  matcher: ["/workspaces/:path*", "/dashboard/:path*", "/onboarding/:path*", "/agents/:path*", "/test/:path*", "/channels/:path*", "/operations/:path*", "/settings/:path*"],
};
