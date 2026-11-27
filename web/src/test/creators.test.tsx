import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router";
import type { CreatorProfile, LedgerEntryView } from "../api/types";
import { ComparePage } from "../pages/ComparePage";
import { CreatorPage } from "../pages/CreatorPage";
import { LedgerPage } from "../pages/LedgerPage";
import { mockFetch, renderWithProviders } from "./utils";

afterEach(() => vi.restoreAllMocks());

const call: LedgerEntryView = {
  entry: {
    id: "led_1",
    check_id: "chk_1",
    claim_id: "clm_1",
    creator: "demo",
    ticker: "KESTREL",
    claim_text: "Kestrel will reach ₹1,500 by March 2027.",
    quote: "Kestrel March 2027 tak ₹1500 jayega",
    direction: "up",
    target_price: 1500,
    target_pct: null,
    made_on: "2026-07-01",
    due_on: "2027-03-31",
    deadline_stated: true,
    baseline_price: 1180,
    status: "hit",
    hit_on: "2027-02-10",
    best_price: 1504.9,
    last_price: 1450,
    last_checked: "2027-03-01",
    price_source: "Demo prices for fictional symbols (not real market data)",
    note: "",
  },
  target: 1500,
  status_description: "The price reached the target on or before the deadline.",
};

function profile(handle: string, overrides: Partial<CreatorProfile> = {}): CreatorProfile {
  return {
    handle,
    checks: 2,
    first_checked: "2026-07-01",
    last_checked: "2026-08-01",
    registration: "Not found in our copy of SEBI's register",
    totals: { misleading: 2, not_verifiable: 3, official_flags: 4, potential_concerns: 1 },
    track_record: {
      claims_checked: 6,
      assessed: 2,
      supported: 0,
      contradicted: 0,
      misleading: 2,
      not_verifiable: 3,
      supported_share: null,
      enough_data: false,
    },
    ledger: { counts: { hit: 1, missed: 0, open: 0, no_data: 0 }, settled: 1, hit_share: null, entries: [call] },
    timeline: [
      { date: "2026-08-01", check_id: "chk_2", official: true, kind: "guaranteed_returns", what: "A promise of guaranteed returns.", quote: "guaranteed 5% har mahine" },
    ],
    recent: [],
    note: "These are facts about checked claims, not a judgement of the person.",
    ...overrides,
  };
}

describe("CreatorPage", () => {
  it("shows the track record, ledger calls and red-flag timeline", async () => {
    mockFetch({ "GET /creators/demo": profile("@demo") });
    renderWithProviders(
      <Routes>
        <Route path="/creators/:handle" element={<CreatorPage />} />
      </Routes>,
      "/creators/demo",
    );
    expect(await screen.findByRole("heading", { name: "@demo" })).toBeInTheDocument();
    expect(screen.getByText(/Too few assessed claims to show a percentage/)).toBeInTheDocument();
    const calls = within(screen.getByRole("list", { name: "Tracked stock calls" }));
    expect(calls.getByText("Target reached")).toBeInTheDocument();
    expect(calls.getByText(/KESTREL · reaches ₹1,500/)).toBeInTheDocument();
    expect(screen.getByText("1 of 1 settled call reached the target.", { exact: false })).toBeInTheDocument();
    const timeline = within(screen.getByRole("list", { name: "Red flags over time" }));
    expect(timeline.getByText(/Official SEBI flag/)).toBeInTheDocument();
  });
});

describe("ComparePage", () => {
  it("puts creators side by side with the not-a-recommendation note", async () => {
    mockFetch({
      "GET /creators/compare?handles=demo&handles=other&handles=ghost": {
        creators: [profile("@demo"), profile("@other", { checks: 5 })],
        missing: ["@ghost"],
        note: "This is not a recommendation to follow, avoid, buy or sell anything.",
      },
    });
    renderWithProviders(<ComparePage />, "/compare?handles=demo,other,ghost");
    expect(await screen.findByRole("note")).toHaveTextContent("not a recommendation");
    const table = screen.getByRole("table");
    expect(within(table).getByRole("columnheader", { name: "@other" })).toBeInTheDocument();
    const row = within(table).getByRole("row", { name: /Checks of their content/ });
    expect(row).toHaveTextContent("25");
    expect(screen.getByText("No checks yet for @ghost.")).toBeInTheDocument();
  });

  it("asks for at least two handles", () => {
    renderWithProviders(<ComparePage />, "/compare");
    expect(screen.getByRole("button", { name: "Compare" })).toBeDisabled();
  });
});

describe("LedgerPage", () => {
  it("explains the rules and lists calls with their creator", async () => {
    mockFetch({
      "GET /ledger": {
        summary: { counts: { hit: 1, missed: 0, open: 0, no_data: 0 }, settled: 1, hit_share: null, entries: [call] },
        note: "Stock calls are tracked from the day PaperTrail first saw them.",
      },
    });
    renderWithProviders(<LedgerPage />, "/ledger");
    expect(await screen.findByRole("link", { name: "@demo" })).toHaveAttribute("href", "/creators/demo");
    expect(screen.getByRole("heading", { name: "How a call is settled" })).toBeInTheDocument();
  });
});
