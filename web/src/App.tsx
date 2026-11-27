import { BrowserRouter, Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { GlossaryProvider } from "./lib/glossary";
import { I18nProvider } from "./lib/i18n";
import { CheckPage } from "./pages/CheckPage";
import { ComparePage } from "./pages/ComparePage";
import { CreatorPage } from "./pages/CreatorPage";
import { GlossaryPage } from "./pages/GlossaryPage";
import { Landing } from "./pages/Landing";
import { LedgerPage } from "./pages/LedgerPage";
import { NewCheck } from "./pages/NewCheck";
import { NotFound } from "./pages/NotFound";
import { RulebookPage } from "./pages/RulebookPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Landing />} />
        <Route path="check" element={<NewCheck />} />
        <Route path="checks/:id" element={<CheckPage />} />
        <Route path="creators/:handle" element={<CreatorPage />} />
        <Route path="compare" element={<ComparePage />} />
        <Route path="ledger" element={<LedgerPage />} />
        <Route path="rulebook" element={<RulebookPage />} />
        <Route path="glossary" element={<GlossaryPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <I18nProvider>
      <GlossaryProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </GlossaryProvider>
    </I18nProvider>
  );
}
