import type { CheckView } from "../api/types";

type Metrics = CheckView["check"]["metrics"];

const STEP_LABELS: Record<string, string> = {
  ingest: "Reading the content",
  extract: "Finding claims",
  registration: "SEBI register",
  research: "Searching for evidence",
  judge: "Weighing evidence",
  rulebook: "SEBI rulebook",
};

const FREE_PROVIDERS = new Set(["groq", "ollama", "mock"]);

function duration(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** How the check ran: time per step, AI calls, models and cost, in plain numbers. */
export function RunDetails({ metrics }: { metrics: Metrics }) {
  const steps = Object.entries(metrics.step_ms ?? {}).filter(([, ms]) => ms > 0);
  const total = steps.reduce((sum, [, ms]) => sum + ms, 0) || 1;
  const provider = metrics.llm_provider ?? "";
  const free = FREE_PROVIDERS.has(provider);
  const models = Array.from(new Set(Object.values(metrics.models ?? {})));

  return (
    <div className="mt-3 space-y-4">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Total time" value={duration(metrics.duration_ms)} />
        <Stat label="AI calls" value={String(metrics.llm_calls)} />
        <Stat label="Text processed (tokens)" value={metrics.total_tokens.toLocaleString("en-IN")} />
        <Stat label="Cost of this check" value={free ? "$0 (free tier)" : `$${metrics.cost_usd.toFixed(4)}`} />
      </dl>
      {steps.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500">Where the time went</p>
          <ul className="mt-1 space-y-1" aria-label="Time per step">
            {steps.map(([name, ms]) => (
              <li key={name} className="flex items-center gap-2 text-xs">
                <span className="w-40 shrink-0 truncate">{STEP_LABELS[name] ?? name}</span>
                <span className="h-2 flex-1 rounded-full bg-slate-100">
                  <span
                    className="block h-2 rounded-full bg-brand-600"
                    style={{ width: `${Math.max(2, (ms / total) * 100)}%` }}
                  />
                </span>
                <span className="w-14 shrink-0 text-right tabular-nums">{duration(ms)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {provider && (
        <p className="text-xs text-slate-500">
          AI provider: {provider}
          {models.length > 0 && ` (${models.join(", ")})`} · {metrics.search_rounds} search round
          {metrics.search_rounds === 1 ? "" : "s"}
        </p>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 px-3 py-2">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-semibold text-ink tabular-nums">{value}</dd>
    </div>
  );
}
