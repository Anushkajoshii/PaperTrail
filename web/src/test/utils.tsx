import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import type { Check, CheckView } from "../api/types";
import { I18nProvider } from "../lib/i18n";
import raw from "./fixtures/check-hinglish.json";

export const fixtureCheck = raw as unknown as Check;

export function viewOf(check: Check, overrides: Partial<CheckView> = {}): CheckView {
  const finished = check.status === "completed" || check.status === "failed";
  return {
    check,
    status_description: "Done. Your results are ready.",
    progress_percent: finished ? 100 : 55,
    is_finished: finished,
    notices: [
      "PaperTrail is not financial advice.",
      "SEBI registration does not mean SEBI endorses anyone's advice.",
      "Confidence is not a guarantee.",
    ],
    verdict_descriptions: {
      supported: "Reliable sources agree with this claim.",
      contradicted: "Reliable sources say the opposite of this claim.",
      misleading: "Partly true, but important missing context changes its meaning.",
      not_verifiable: "We could not find enough reliable evidence either way.",
    },
    ...overrides,
  };
}

export function renderWithProviders(ui: ReactElement, route = "/") {
  return render(
    <I18nProvider>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </I18nProvider>,
  );
}

/** Replace global fetch with a router of JSON responses keyed by "METHOD path". */
export function mockFetch(routes: Record<string, unknown>) {
  const calls: { method: string; path: string; body?: unknown }[] = [];
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const path = url.replace(/^\/api/, "");
    const method = init?.method ?? "GET";
    calls.push({ method, path, body: init?.body });
    const key = `${method} ${path}`;
    if (!(key in routes)) return new Response(JSON.stringify({ error: { code: "not_found", message: "No route" } }), { status: 404 });
    return new Response(JSON.stringify(routes[key]), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  return calls;
}
