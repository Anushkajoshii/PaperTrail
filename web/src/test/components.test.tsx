import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfidenceMeter, ClaimCard } from "../components/ClaimCard";
import { ProgressView } from "../components/ProgressView";
import { ResultsView } from "../components/ResultsView";
import { VerdictBadge } from "../components/VerdictBadge";
import { fixtureCheck, renderWithProviders, viewOf } from "./utils";

describe("VerdictBadge", () => {
  it("shows the label as text, not colour alone", () => {
    render(<VerdictBadge label="contradicted" />);
    expect(screen.getByText("Contradicted")).toBeInTheDocument();
  });
});

describe("ConfidenceMeter", () => {
  it("exposes the value and band to screen readers", () => {
    render(<ConfidenceMeter value={0.82} />);
    const meter = screen.getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuenow", "82");
    expect(meter).toHaveAccessibleName(/High/);
  });
});

describe("ClaimCard", () => {
  it("replaces internal evidence ids with readable source numbers", async () => {
    const claim = fixtureCheck.claims.find((c) => c.claim_type === "return_promise")!;
    const verdict = fixtureCheck.verdicts.find((v) => v.claim_id === claim.id)!;
    const evidence = fixtureCheck.evidence.filter((e) => e.claim_id === claim.id);
    renderWithProviders(<ClaimCard claim={claim} verdict={verdict} evidence={evidence} index={0} />);
    expect(screen.getByText(/Official guidance \(source 1\)/)).toBeInTheDocument();
    expect(screen.queryByText(/evd_/)).not.toBeInTheDocument();
    expect(screen.getByText("Source 1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Hide details/ }));
    expect(screen.getByRole("button", { name: /Why this verdict/ })).toHaveAttribute("aria-expanded", "false");
  });
});

describe("ResultsView", () => {
  it("summarises verdicts, separates official flags from AI concerns and shows notices", () => {
    renderWithProviders(<ResultsView view={viewOf(fixtureCheck)} />);
    expect(screen.getByRole("heading", { name: /4 claims checked from @demo_finfluencer/ })).toBeInTheDocument();
    const glance = screen.getByRole("region", { name: "At a glance" });
    expect(within(glance).getByText("Misleading")).toBeInTheDocument();
    expect(screen.getByText(/5\b/, { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Registration not checked" })).toBeInTheDocument();
    expect(screen.getByText("PaperTrail is not financial advice.")).toBeInTheDocument();
    // Most serious verdicts come first: the misleading claim leads the list.
    const claims = screen.getByRole("region", { name: "Claims and verdicts" });
    expect(within(claims).getAllByRole("article")[0]).toHaveTextContent("Misleading");
  });
});

describe("ProgressView", () => {
  it("marks finished, active and waiting steps", () => {
    const running = { ...fixtureCheck, status: "researching" as const, status_detail: "Looking for evidence (round 1)" };
    renderWithProviders(<ProgressView view={viewOf(running)} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "55");
    expect(screen.getByText("Looking for evidence (round 1)")).toBeInTheDocument();
    expect(screen.getByText(/Finding the claims/).textContent).toMatch(/done/);
    expect(screen.getByText(/Weighing the evidence/).textContent).toMatch(/waiting/);
  });
});

describe("ShareBar", () => {
  it("links to the report formats and builds a neutral WhatsApp summary", async () => {
    const { ShareBar, shareText } = await import("../components/ShareBar");
    renderWithProviders(<ShareBar check={fixtureCheck} />);
    expect(screen.getByRole("link", { name: /Save as PDF/ })).toHaveAttribute("href", `/api/checks/${fixtureCheck.id}/report?format=html&print=true`);
    expect(screen.getByRole("link", { name: /Download report/ })).toHaveAttribute("href", expect.stringContaining("download=true"));
    expect(screen.getByRole("link", { name: /Markdown/ })).toHaveAttribute("href", expect.stringContaining("format=md"));
    expect(screen.getByRole("link", { name: /WhatsApp/ }).getAttribute("href")).toMatch(/^https:\/\/wa\.me\/\?text=/);
    const text = shareText(fixtureCheck, "https://papertrail.example/checks/x");
    expect(text).toContain("4 claims checked");
    expect(text).toContain("1 misleading");
    expect(text).toContain("Not financial advice");
    expect(text).not.toMatch(/scam|fraud|liar/i);
  });
});
