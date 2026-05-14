"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import RatingForm from "@/components/RatingForm";
import ResultsDashboard from "@/components/ResultsDashboard";
import { validateFieldValue } from "@/lib/validation/inputValidation";

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
  workbook_local_path?: string;
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
  const [validationErrors, setValidationErrors] = useState<Record<string, string | undefined>>({});
  const [validationWarnings, setValidationWarnings] = useState<Record<string, string | undefined>>({});

  useEffect(() => {
    fetch(`/api/raters/${slug}/config`)
      .then(async (r) => ({ ok: r.ok, status: r.status, data: await r.json() }))
      .then(({ ok, status, data }) => {
        const loadedConfig =
          data?.config ??
          data?.rater?.config ??
          data?.data?.config ??
          data?.data?.rater?.config;
        if (!ok || !loadedConfig) {
          const detail = data?.detail ?? data?.data?.detail;
          throw new Error(
            typeof detail === "string"
              ? detail
              : `Failed to load rater config (${status})`
          );
        }

        const workbookPath = data?.rater?.workbook_local_path;
        const resolvedConfig = workbookPath
          ? { ...loadedConfig, workbook_local_path: workbookPath }
          : loadedConfig;
        setConfig(resolvedConfig);
        // Seed defaults
        const defaults: Record<string, string | number | boolean | null | undefined> = {};
        loadedConfig.inputs?.forEach((f: FieldDef) => {
          defaults[f.field] = f.default ?? "";
        });
        setInputs(defaults);
        setValidationErrors({});
        setValidationWarnings({});
      })
      .catch((err: unknown) =>
        setError(
          err instanceof Error ? err.message : "Failed to load rater config."
        )
      )
      .finally(() => setLoading(false));
  }, [slug]);

  async function handleCalculate() {
    if (!config) return;
    setCalculating(true);
    setOutputs(null);
    setDownloadUrl(null);
    setError("");

    try {
      try {
        await fetch("http://localhost:8000/api/validation/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inputs, config }),
        });
      } catch (err) {
        console.warn("Validation failed", err);
      }

      const res = await fetch(`/api/raters/${slug}/calculate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inputs }),
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = data?.detail ?? data?.data?.detail;
        setError(
          typeof detail === "string"
            ? detail
            : `Calculation failed (${res.status})`
        );
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

  function handleInputChange(
    field: string,
    value: string | number | boolean | null | undefined
  ) {
    setInputs((prev) => ({ ...prev, [field]: value }));

    if (!config) return;
    const fieldDef = config.inputs?.find((item) => item.field === field);
    if (!fieldDef) return;

    const { error, warning } = validateFieldValue(fieldDef, value);
    setValidationErrors((prev) => ({ ...prev, [field]: error }));
    setValidationWarnings((prev) => ({ ...prev, [field]: warning }));
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
            onChange={handleInputChange}
            errors={validationErrors}
            warnings={validationWarnings}
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
