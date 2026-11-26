import { Check as CheckIcon, LoaderCircle } from "lucide-react";
import type { CheckStatus, CheckView } from "../api/types";
import { useI18n } from "../lib/i18n";

const STEPS: { status: CheckStatus; title: string; body: string }[] = [
  { status: "transcribing", title: "Reading the content", body: "Turning speech or the page into text." },
  { status: "extracting", title: "Finding the claims", body: "Picking out statements that can be checked, with the exact words used." },
  { status: "researching", title: "Looking for evidence", body: "Searching exchanges, filings, regulators and established news." },
  { status: "judging", title: "Weighing the evidence", body: "Deciding what supports or contradicts each claim, and how strongly." },
  { status: "checking_rulebook", title: "Checking the SEBI rulebook", body: "Comparing what was said with official SEBI rules and guidance." },
];
const ORDER: CheckStatus[] = ["queued", ...STEPS.map((s) => s.status), "completed"];

export function ProgressView({ view }: { view: CheckView }) {
  const { t } = useI18n();
  const current = ORDER.indexOf(view.check.status);
  return (
    <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
      <div className="card p-8">
        <p className="eyebrow">Check {view.check.id}</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">{t("progress.title")}</h1>
        <p className="mt-2 text-slate-600">{t("progress.subtitle")}</p>

        <div className="mt-6 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={view.progress_percent} aria-label="Progress">
          <div className="h-full rounded-full bg-brand-500 transition-all duration-700" style={{ width: `${view.progress_percent}%` }} />
        </div>

        <ol className="mt-8 space-y-5" aria-live="polite">
          {STEPS.map((step) => {
            const idx = ORDER.indexOf(step.status);
            const state = idx < current ? "done" : idx === current ? "active" : "waiting";
            return (
              <li key={step.status} className="flex gap-4">
                <span
                  className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 ${
                    state === "done" ? "border-brand-500 bg-brand-500 text-white" : state === "active" ? "border-brand-500 text-brand-600" : "border-slate-200 text-slate-300"
                  }`}
                  aria-hidden="true"
                >
                  {state === "done" ? <CheckIcon className="h-4 w-4" /> : state === "active" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                </span>
                <div>
                  <p className={`font-medium ${state === "waiting" ? "text-slate-400" : "text-ink"}`}>
                    {step.title}
                    <span className="sr-only">: {state === "done" ? "done" : state === "active" ? "in progress" : "waiting"}</span>
                  </p>
                  <p className={`text-sm ${state === "waiting" ? "text-slate-400" : "text-slate-600"}`}>
                    {state === "active" && view.check.status_detail ? view.check.status_detail : step.body}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
        {view.check.status === "queued" && <p className="mt-6 text-sm text-slate-500">{view.status_description}</p>}
      </div>
    </div>
  );
}
