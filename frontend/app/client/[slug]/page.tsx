"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import RatingForm from "@/components/RatingForm";
import ResultsDashboard from "@/components/ResultsDashboard";

interface FieldDef {
  field: string;
  cell: string;
  type: string;
  label: string;
  description: string;
  group: string;
  options: string[];
  default: string | number | boolean | null | undefined;
  primary: boolean;
}

interface RaterConfig {
  slug: string;
  name: string;
  sheet: string;
  inputs: FieldDef[];
  outputs: FieldDef[];
}

export default function ClientRaterPage() {
  const { slug } = useParams<{ slug: string }>();
  const [config, setConfig] = useState<RaterConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [inputs, setInputs] = useState<Record<string, string | number | boolean | null | undefined>>({});
  const [outputs, setOutputs] = useState<Record<string, string | number | boolean | null | undefined> | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/raters/${slug}/config`)
      .then(async (r) => ({ ok: r.ok, status: r.status, data: await r.json() }))
      .then((data) => {
<<<<<<< Updated upstream
        const loadedConfig = data.config ?? data.rater?.config;
        setConfig(loadedConfig);
        // Seed defaults
        const defaults: Record<string, string | number | boolean | null | undefined> = {};
        loadedConfig?.inputs?.forEach((f: FieldDef) => {
=======
        const config = data.data?.config ?? data.data?.rater?.config;
        if (!data.ok || !config) {
          throw new Error(
            typeof data.data?.detail === "string"
              ? data.data.detail
              : `Failed to load rater config (${data.status})`
          );
        }

        setConfig(config);
        // Seed defaults
        const defaults: Record<string, any> = {};
        config.inputs?.forEach((f: FieldDef) => {
>>>>>>> Stashed changes
          defaults[f.field] = f.default ?? "";
        });
        setInputs(defaults);
      })
      .catch(() => setError("Failed to load rater config."))
      .finally(() => setLoading(false));
  }, [slug]);

  async function handleCalculate() {
    if (!config) return;
    setCalculating(true);
    setOutputs(null);
    setDownloadUrl(null);
    setError("");

    try {
      const res = await fetch(`/api/raters/${slug}/calculate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inputs }),
      });
      const data = await res.json();
      if (!res.ok) {
<<<<<<< Updated upstream
        setError(data.detail ?? "Calculation failed. Please try again.");
=======
        setError(
          typeof data.detail === "string"
            ? data.detail
            : `Calculation failed (${res.status})`
        );
>>>>>>> Stashed changes
        return;
      }
      setOutputs(data.outputs);
      if (data.download_url) setDownloadUrl(data.download_url);
    } catch {
      setError("Calculation failed. Please try again.");
    } finally {
      setCalculating(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-background p-8">
        <div className="max-w-3xl mx-auto space-y-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-96 w-full rounded-2xl" />
        </div>
      </main>
    );
  }

  if (error && !config) {
    return (
      <main className="min-h-screen bg-background p-8">
        <div className="max-w-3xl mx-auto text-center py-24">
          <p className="text-destructive">{error}</p>
          <Link href="/client">
            <Button variant="outline" className="mt-4">← Back</Button>
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">{config?.name}</h1>
            <p className="text-muted-foreground mt-1 capitalize">
              {config?.sheet}
            </p>
          </div>
          <Link href="/client">
            <Button variant="outline">← Back</Button>
          </Link>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
            {error}
          </div>
        )}

        {config && (
          <RatingForm
            inputs={config.inputs}
            values={inputs}
            onChange={(field, value) =>
              setInputs((prev) => ({ ...prev, [field]: value }))
            }
          />
        )}

        <Button
          className="w-full mt-6"
          size="lg"
          onClick={handleCalculate}
          disabled={calculating}
        >
          {calculating ? "Calculating…" : "Calculate Premium"}
        </Button>

        {outputs && (
          <div className="mt-8">
            <ResultsDashboard
              outputs={config?.outputs ?? []}
              values={outputs}
              downloadUrl={downloadUrl}
            />
          </div>
        )}
      </div>
    </main>
  );
}
