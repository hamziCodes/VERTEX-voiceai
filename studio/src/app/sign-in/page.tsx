import { startSignInAction } from "@/features/workspaces/actions";

interface SignInPageProps {
  searchParams: Promise<{ invitation?: string }>;
}

export default async function SignInPage({ searchParams }: SignInPageProps) {
  const { invitation = "" } = await searchParams;
  return (
    <main>
      <p>Wavia Studio</p>
      <h1>Sign in to your workspace</h1>
      <p>Continue through WorkOS. Your provider token remains in an encrypted, HTTP-only session cookie.</p>
      <form action={startSignInAction}>
        {invitation ? <input name="invitation" type="hidden" value={invitation} /> : null}
        <button type="submit">Continue securely</button>
      </form>
    </main>
  );
}
