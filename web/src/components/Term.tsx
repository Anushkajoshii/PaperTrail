import { useId, useState, type ReactNode } from "react";
import { useDefinition } from "../lib/glossary";

/**
 * A glossary term with an accessible tooltip: hover, keyboard focus or tap shows the
 * plain-language definition. Falls back to plain text if the glossary isn't loaded.
 */
export function Term({ term, children }: { term: string; children?: ReactNode }) {
  const definition = useDefinition(term);
  const [open, setOpen] = useState(false);
  const id = useId();
  if (!definition) return <>{children ?? term}</>;
  return (
    <span className="relative inline-block">
      <button
        type="button"
        className="cursor-help border-b border-dotted border-current/60 text-left font-inherit"
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
      >
        {children ?? term}
      </button>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute bottom-full left-1/2 z-30 mb-2 w-64 -translate-x-1/2 rounded-xl bg-ink px-3 py-2 text-xs leading-relaxed font-normal text-white shadow-lg"
        >
          <span className="mb-0.5 block font-semibold">{term}</span>
          {definition}
        </span>
      )}
    </span>
  );
}
