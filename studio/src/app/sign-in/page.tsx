import { startSignInAction, startSignUpAction } from "@/features/workspaces/actions";

interface SignInPageProps {
  searchParams: Promise<{ invitation?: string }>;
}

export default async function SignInPage({ searchParams }: SignInPageProps) {
  const { invitation = "" } = await searchParams;
  return (
    <main className="entry-shell">
      <section className="entry-panel entry-panel--auth">
        <div className="entry-wordmark"><span aria-hidden="true">W</span> Wavia Studio</div>
        <div className="entry-panel__content">
          <p className="screen-eyebrow">Secure workspace access</p>
          <h1>Sign in to Wavia Studio</h1>
          <p className="entry-lede">Continue through your organization&apos;s secure sign-in. Your session stays in an encrypted, HTTP-only cookie.</p>
          {invitation ? <p className="entry-invitation">Your workspace invitation will be ready after sign-in.</p> : null}
          <form action={startSignInAction}>
            {invitation ? <input name="invitation" type="hidden" value={invitation} /> : null}
            <button className="button button--primary button--wide" type="submit">Continue securely</button>
          </form>
          <form action={startSignUpAction} className="entry-alt-action">
            {invitation ? <input name="invitation" type="hidden" value={invitation} /> : null}
            <span>New to Wavia?</span>{" "}
            <button className="button button--secondary" type="submit">Create an account</button>
          </form>
        </div>
        <p className="entry-footnote">Wavia does not place a call or contact a voice provider when you sign in.</p>
      </section>
    </main>
  );
}
