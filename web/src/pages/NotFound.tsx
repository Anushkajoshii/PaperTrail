import { Link } from "react-router";

export function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <p className="eyebrow">404</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">This page doesn't exist</h1>
      <p className="mt-3 text-slate-600">The link may be wrong, or the page may have moved.</p>
      <Link to="/" className="btn-primary mt-8">
        Go to the home page
      </Link>
    </div>
  );
}
