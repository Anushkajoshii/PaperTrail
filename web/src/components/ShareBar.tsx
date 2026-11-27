import { Copy, Download, FileText, MessageCircle, Printer } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import type { Check } from "../api/types";
import { VERDICTS } from "../lib/verdicts";

/** Short, neutral summary for sharing. It describes claims, never the person. */
export function shareText(check: Check, link: string): string {
  const counts = check.verdicts.reduce<Record<string, number>>((acc, v) => {
    acc[v.label] = (acc[v.label] ?? 0) + 1;
    return acc;
  }, {});
  const parts = Object.entries(counts).map(([label, n]) => `${n} ${VERDICTS[label as keyof typeof VERDICTS].label.toLowerCase()}`);
  const official = check.red_flags.filter((f) => f.basis === "verified_rule").length;
  const who = check.input.creator_handle ? ` of content from ${check.input.creator_handle}` : "";
  return (
    `PaperTrail fact-check${who}: ${check.claims.length} claim${check.claims.length === 1 ? "" : "s"} checked` +
    (parts.length ? ` (${parts.join(", ")})` : "") +
    `; ${official} official SEBI red flag${official === 1 ? "" : "s"}. ` +
    `Sources and reasoning: ${link} (Not financial advice.)`
  );
}

export function ShareBar({ check }: { check: Check }) {
  const [copied, setCopied] = useState(false);
  const link = typeof window !== "undefined" ? window.location.href : "";
  const whatsapp = `https://wa.me/?text=${encodeURIComponent(shareText(check, link))}`;
  const item = "btn-secondary px-4 py-2.5";
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Save and share">
      <a className={item} href={api.reportUrl(check.id, { print: true })} target="_blank" rel="noopener">
        <Printer className="h-4 w-4" aria-hidden="true" /> Save as PDF
      </a>
      <a className={item} href={api.reportUrl(check.id, { download: true })}>
        <Download className="h-4 w-4" aria-hidden="true" /> Download report
      </a>
      <a className={item} href={api.reportUrl(check.id, { format: "md", download: true })}>
        <FileText className="h-4 w-4" aria-hidden="true" /> Markdown
      </a>
      <a className={item} href={whatsapp} target="_blank" rel="noopener noreferrer">
        <MessageCircle className="h-4 w-4" aria-hidden="true" /> Share on WhatsApp
      </a>
      <button
        type="button"
        className={item}
        onClick={() => {
          void navigator.clipboard?.writeText(link);
          setCopied(true);
        }}
      >
        <Copy className="h-4 w-4" aria-hidden="true" /> {copied ? "Link copied" : "Copy link"}
      </button>
    </div>
  );
}
