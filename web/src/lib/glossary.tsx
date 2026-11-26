import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { GlossaryTerm } from "../api/types";

const Ctx = createContext<Map<string, string>>(new Map());

/** Loads the plain-language glossary once from the API for tooltips across the app. */
export function GlossaryProvider({ children }: { children: ReactNode }) {
  const [terms, setTerms] = useState<Map<string, string>>(new Map());
  useEffect(() => {
    api
      .getGlossary()
      .then((list: GlossaryTerm[]) => setTerms(new Map(list.map((t) => [t.term.toLowerCase(), t.definition]))))
      .catch(() => setTerms(new Map()));
  }, []);
  return <Ctx.Provider value={terms}>{children}</Ctx.Provider>;
}

export function useDefinition(term: string): string | undefined {
  return useContext(Ctx).get(term.toLowerCase());
}
