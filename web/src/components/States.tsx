import { AlertCircle, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-20 text-slate-500">
      <LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div role="alert" className="mx-auto max-w-xl px-4 py-20 text-center">
      <AlertCircle className="mx-auto h-10 w-10 text-contradicted" aria-hidden="true" />
      <h1 className="mt-4 text-xl font-semibold">{title}</h1>
      {children && <div className="mt-2 text-slate-600">{children}</div>}
      <Link to="/check" className="btn-primary mt-6">
        Start a new check
      </Link>
    </div>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-8">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
      {children && <div className="mt-3 max-w-3xl text-lg leading-relaxed text-slate-600">{children}</div>}
    </div>
  );
}
