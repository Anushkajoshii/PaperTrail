import type {
  CheckAccepted,
  CheckView,
  CreateCheckRequest,
  CreatorView,
  GlossaryTerm,
  Language,
  RulebookResponse,
} from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public retryAfter?: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "network", "Could not reach PaperTrail. Check your connection and try again.");
  }
  if (!res.ok) {
    let code = "error";
    let message = `Something went wrong (HTTP ${res.status}).`;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      /* not JSON */
    }
    const retry = Number(res.headers.get("retry-after")) || undefined;
    throw new ApiError(res.status, code, message, retry);
  }
  return (await res.json()) as T;
}

export const api = {
  createCheck: (body: CreateCheckRequest) =>
    request<CheckAccepted>("/checks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  uploadCheck: (file: File, opts: { creatorHandle?: string; creatorName?: string; language?: Language }) => {
    const form = new FormData();
    form.append("file", file);
    if (opts.creatorHandle) form.append("creator_handle", opts.creatorHandle);
    if (opts.creatorName) form.append("creator_name", opts.creatorName);
    if (opts.language) form.append("language_hint", opts.language);
    return request<CheckAccepted>("/checks/upload", { method: "POST", body: form });
  },

  getCheck: (id: string) => request<CheckView>(`/checks/${encodeURIComponent(id)}`),
  getCreator: (handle: string) => request<CreatorView>(`/creators/${encodeURIComponent(handle)}`),
  getRulebook: () => request<RulebookResponse>("/rulebook"),
  getGlossary: () => request<GlossaryTerm[]>("/glossary"),

  /** Plain URL for a report: open it, download it, or open the print dialog (Save as PDF). */
  reportUrl: (id: string, opts: { format?: "html" | "md"; download?: boolean; print?: boolean } = {}) => {
    const q = new URLSearchParams({ format: opts.format ?? "html" });
    if (opts.download) q.set("download", "true");
    if (opts.print) q.set("print", "true");
    return `${BASE}/checks/${encodeURIComponent(id)}/report?${q}`;
  },
};
