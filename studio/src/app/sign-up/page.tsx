import Link from "next/link";

import { startSignUpAction } from "@/features/workspaces/actions";

interface SignUpPageProps {
  searchParams: Promise<{ invitation?: string }>;
}

export default async function SignUpPage({ searchParams }: SignUpPageProps) {
  const { invitation = "" } = await searchParams;
  return (
    <main className="entry-shell">
      <section className="entry-panel entry-panel--auth">
        <div className="entry-wordmark"><span aria-hidden="true">W</span> Wavia Studio</div>
        <div className="entry-panel__content">
          <p className="screen-eyebrow">Create your account</p>
          <h1>Start building with Wavia</h1>
          <p className="entry-lede">Create an account through secure hosted sign-up; you will verify your email there. Then create a workspace and build your first voice agent.</p>
          {invitation ? <p className="entry-invitation">Your workspace invitation will be ready after sign-up.</p> : null}
          <form action={startSignUpAction}>
            {invitation ? <input name="invitation" type="hidden" value={invitation} /> : null}
            <button className="button button--primary button--wide" type="submit">Create an account</button>
          </form>
          <p className="entry-alt-action">Already have an account? <Link href={invitation ? `/sign-in?invitation=${encodeURIComponent(invitation)}` : "/sign-in"}>Sign in</Link></p>
        </div>
        <p className="entry-footnote">Wavia does not place a call or contact a voice provider when you sign up.</p>
      </section>
    </main>
  );
}
