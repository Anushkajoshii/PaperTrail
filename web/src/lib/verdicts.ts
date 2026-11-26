import { CircleCheck, CircleHelp, CircleX, TriangleAlert, type LucideIcon } from "lucide-react";
import type { VerdictLabel } from "../api/types";

export interface VerdictStyle {
  label: string;
  short: string;
  icon: LucideIcon;
  text: string; // tailwind text colour class
  bg: string;
  ring: string;
}

export const VERDICTS: Record<VerdictLabel, VerdictStyle> = {
  supported: {
    label: "Supported",
    short: "Reliable sources agree",
    icon: CircleCheck,
    text: "text-supported",
    bg: "bg-supported-bg",
    ring: "ring-supported/20",
  },
  contradicted: {
    label: "Contradicted",
    short: "Reliable sources disagree",
    icon: CircleX,
    text: "text-contradicted",
    bg: "bg-contradicted-bg",
    ring: "ring-contradicted/20",
  },
  misleading: {
    label: "Misleading",
    short: "Missing context changes the meaning",
    icon: TriangleAlert,
    text: "text-misleading",
    bg: "bg-misleading-bg",
    ring: "ring-misleading/20",
  },
  not_verifiable: {
    label: "Not verifiable",
    short: "Not enough reliable evidence either way",
    icon: CircleHelp,
    text: "text-unverifiable",
    bg: "bg-unverifiable-bg",
    ring: "ring-unverifiable/20",
  },
};

export const VERDICT_ORDER: VerdictLabel[] = ["contradicted", "misleading", "not_verifiable", "supported"];

export const CLAIM_TYPE_LABELS: Record<string, string> = {
  past_performance: "Past performance",
  return_promise: "Return promise",
  stock_call: "Stock call",
  market_fact: "Market fact",
  company_fact: "Company fact",
  credential: "Credential",
  other: "Other fact",
};

export const STANCE_LABELS: Record<string, string> = {
  supports: "Supports the claim",
  contradicts: "Contradicts the claim",
  context: "Useful context",
};

export function band(score: number): "High" | "Medium" | "Low" {
  return score >= 0.75 ? "High" : score >= 0.45 ? "Medium" : "Low";
}

export function formatTimestamp(seconds?: number | null): string | null {
  if (seconds == null) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "Date not stated";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
