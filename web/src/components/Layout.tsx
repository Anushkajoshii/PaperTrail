import { Languages, Menu, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { useI18n } from "../lib/i18n";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill={light ? "#fff" : "#0f3d3e"} />
        <path d="M10 7h9l5 5v13a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z" fill={light ? "#0f3d3e" : "#fff"} />
        <path d="M12.5 18.5l2.5 2.5 5-5" stroke="#14b8a6" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className={`text-lg font-bold tracking-tight ${light ? "text-white" : "text-ink"}`}>PaperTrail</span>
    </span>
  );
}

export function Layout() {
  const { t, lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const links = [
    { to: "/check", label: t("nav.check") },
    { to: "/ledger", label: t("nav.ledger") },
    { to: "/rulebook", label: t("nav.rulebook") },
    { to: "/glossary", label: t("nav.glossary") },
  ];
  const navClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium transition ${isActive ? "bg-brand-50 text-brand-900" : "text-slate-600 hover:text-ink"}`;

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link to="/" aria-label="PaperTrail home" onClick={() => setOpen(false)}>
            <Logo />
          </Link>
          <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} className={navClass}>
                {l.label}
              </NavLink>
            ))}
            <button
              type="button"
              onClick={() => setLang(lang === "en" ? "hi" : "en")}
              className="ml-2 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:border-brand-600"
              aria-label="Switch interface language"
            >
              <Languages className="h-4 w-4" aria-hidden="true" /> {t("lang.toggle")}
            </button>
          </nav>
          <button
            type="button"
            className="rounded-lg p-2 md:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
        {open && (
          <nav className="border-t border-slate-200 bg-white px-4 py-3 md:hidden" aria-label="Mobile">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} className={(s) => `${navClass(s)} block`} onClick={() => setOpen(false)}>
                {l.label}
              </NavLink>
            ))}
            <button
              type="button"
              onClick={() => setLang(lang === "en" ? "hi" : "en")}
              className="mt-1 flex w-full items-center gap-1.5 rounded-lg px-3 py-2 text-left text-sm font-medium text-brand-700"
            >
              <Languages className="h-4 w-4" aria-hidden="true" /> {t("lang.toggle")}
            </button>
          </nav>
        )}
      </header>

      <main id="main" className="flex-1" key={location.pathname}>
        <Outlet />
      </main>

      <footer className="mt-16 bg-brand-900 text-slate-300">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-3">
          <div>
            <Logo light />
            <p className="mt-3 text-sm leading-relaxed">Evidence-backed fact-checking for Indian finance content.</p>
          </div>
          <div className="text-sm md:col-span-2">
            <p className="leading-relaxed">{t("footer.disclaimer")}</p>
            <p className="mt-3 leading-relaxed">
              SEBI registration does not mean SEBI endorses anyone's advice. Verify registrations on{" "}
              <a className="underline hover:text-white" href="https://www.sebi.gov.in/intermediaries.html" target="_blank" rel="noreferrer">
                sebi.gov.in
              </a>{" "}
              and report suspicious activity on SEBI's{" "}
              <a className="underline hover:text-white" href="https://mi.sebi.gov.in/" target="_blank" rel="noreferrer">
                Market Intelligence portal
              </a>
              .
            </p>
          </div>
        </div>
        <div className="border-t border-white/10">
          <p className="mx-auto max-w-6xl px-4 py-4 text-xs text-slate-400 sm:px-6">
            © {new Date().getFullYear()} Anushka Joshi
          </p>
        </div>
      </footer>
    </div>
  );
}
