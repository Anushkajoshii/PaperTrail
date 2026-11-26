import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { ApiError, api } from "../api/client";
import type { CheckView } from "../api/types";
import { ProgressView } from "../components/ProgressView";
import { ResultsView } from "../components/ResultsView";
import { ErrorState, Spinner } from "../components/States";

const POLL_MS = 1500;

export function CheckPage() {
  const { id = "" } = useParams();
  const [view, setView] = useState<CheckView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const v = await api.getCheck(id);
        if (cancelled) return;
        setView(v);
        if (!v.is_finished) timer = setTimeout(poll, POLL_MS);
      } catch (e) {
        if (!cancelled) setError(e as ApiError);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id]);

  if (error) {
    return <ErrorState title={error.status === 404 ? "We couldn't find that check" : "Something went wrong"}>{error.message}</ErrorState>;
  }
  if (!view) return <Spinner label="Loading the check" />;
  if (view.check.status === "failed") {
    return (
      <ErrorState title="This check could not be completed">
        <p>{view.check.error}</p>
        <p className="mt-2 text-sm">No partial results are shown, so you never see half a fact-check.</p>
      </ErrorState>
    );
  }
  if (!view.is_finished) return <ProgressView view={view} />;
  return <ResultsView view={view} />;
}
