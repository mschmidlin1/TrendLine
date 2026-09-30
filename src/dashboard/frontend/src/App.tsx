import { useEffect, useState } from "react";

type HelloResponse = {
  message: string;
};

export default function App() {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/hello")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`API returned ${response.status}`);
        }
        return (await response.json()) as HelloResponse;
      })
      .then((body) => {
        if (!cancelled) {
          setMessage(body.message);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const detail = err instanceof Error ? err.message : "Unknown error";
          setError(`Could not reach the dashboard API. ${detail}`);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 p-8 text-slate-100">
      <section className="max-w-lg text-center">
        <h1 className="text-3xl font-semibold tracking-tight">TrendLine Dashboard</h1>
        <p className="mt-4 text-slate-300">{error ?? message ?? "Loading..."}</p>
      </section>
    </main>
  );
}
