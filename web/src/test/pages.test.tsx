import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { Layout } from "../components/Layout";
import { Term } from "../components/Term";
import { GlossaryProvider } from "../lib/glossary";
import { CheckPage } from "../pages/CheckPage";
import { NewCheck } from "../pages/NewCheck";
import { fixtureCheck, mockFetch, renderWithProviders, viewOf } from "./utils";

afterEach(() => vi.restoreAllMocks());

describe("NewCheck", () => {
  it("submits a sample and navigates to the check page", async () => {
    const calls = mockFetch({
      "POST /checks": { id: "chk_1", status: "queued", status_description: "", status_url: "/checks/chk_1", poll_after_seconds: 2 },
      "GET /checks/chk_1": viewOf(fixtureCheck),
    });
    renderWithProviders(
      <Routes>
        <Route path="/check" element={<NewCheck />} />
        <Route path="/checks/:id" element={<CheckPage />} />
      </Routes>,
      "/check",
    );
    const submit = screen.getByRole("button", { name: "Start check" });
    expect(submit).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Hinglish reel" }));
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    expect(await screen.findByRole("heading", { name: /claims checked/ })).toBeInTheDocument();
    const body = JSON.parse(String(calls[0].body));
    expect(body).toMatchObject({ kind: "text", creator_handle: "@demo_finfluencer" });
  });

  it("shows a friendly message when rate limited", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ error: { code: "rate_limited", message: "Too many" } }), { status: 429, headers: { "Retry-After": "30" } }),
    ) as typeof fetch;
    renderWithProviders(<NewCheck />);
    await userEvent.type(screen.getByLabelText("Content to check"), "Guaranteed 10% every month");
    await userEvent.click(screen.getByRole("button", { name: "Start check" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("wait 30 seconds");
  });
});

describe("CheckPage", () => {
  it("shows a clear error for failed checks, never partial results", async () => {
    mockFetch({ "GET /checks/chk_x": viewOf({ ...fixtureCheck, status: "failed", error: "The content is empty", verdicts: [] }) });
    renderWithProviders(
      <Routes>
        <Route path="/checks/:id" element={<CheckPage />} />
      </Routes>,
      "/checks/chk_x",
    );
    expect(await screen.findByText("This check could not be completed")).toBeInTheDocument();
    expect(screen.getByText("The content is empty")).toBeInTheDocument();
  });
});

describe("Glossary tooltips and language", () => {
  it("shows a definition on hover", async () => {
    mockFetch({ "GET /glossary": [{ term: "Confidence", definition: "How strongly the evidence backs the assessment." }] });
    renderWithProviders(
      <GlossaryProvider>
        <Term term="Confidence" />
      </GlossaryProvider>,
    );
    const trigger = await screen.findByRole("button", { name: "Confidence" });
    await userEvent.hover(trigger);
    expect(screen.getByRole("tooltip")).toHaveTextContent("How strongly the evidence");
  });

  it("switches the interface to Hindi", async () => {
    mockFetch({});
    renderWithProviders(
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<p>home</p>} />
        </Route>
      </Routes>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Switch interface language" }));
    await waitFor(() => expect(screen.getAllByText("सेबी नियम-पुस्तिका").length).toBeGreaterThan(0));
    expect(document.documentElement.lang).toBe("hi");
  });
});
