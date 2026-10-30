import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main>
      <h1>Page not found</h1>
      <p>The Studio page you requested does not exist.</p>
      <Link href="/">Return to Studio</Link>
    </main>
  );
}
