"use client";
import { useState, useCallback, useRef } from "react";

import { useDropzone } from "react-dropzone";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import NoSchemaFallback from "@/components/NoSchemaFallback";
import EngineSelector from "@/components/EngineSelector";

type Engine = "excel" | "schema";
type Step = 1 | 2 | 3 | 4;

interface FieldDef {
  field: string;
  cell: string;
  type: string;
  label: string;
  description: string;
  group: string;
  options: string[];
  default: any;
  direction: string;
  primary: boolean;
}

interface ParsedConfig {
  slug: string;
  name: string;
  sheet: string;
  inputs: FieldDef[];
  outputs: FieldDef[];
}

export default function UploadPage() {
  const [step, setStep] = useState<Step>(1);
  const [engine, setEngine] = useState<Engine | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState("");
  const [warmStatus, setWarmStatus] = useState("");
  const [parsedConfig, setParsedConfig] = useState<ParsedConfig | null>(null);
  const [raterName, setRaterName] = useState("");
  const [raterType, setRaterType] = useState("custom");
  const [testInputs, setTestInputs] = useState<Record<string, any>>({});
  const [testOutputs, setTestOutputs] = useState<Record<string, any> | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [noSchemaDetected, setNoSchemaDetected] = useState(false);

  // ── Step 1: Drop zone ────────────────────────────────────────────────────
  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"] },
    maxFiles: 1,
  });

  // ── Upload to backend ────────────────────────────────────────────────────
 async function handleUpload() {
  if (!file || !engine) return;
  setError("");

  const fd = new FormData();
  fd.append("file", file);

  const endpoint =
    engine === "excel" ? "/api/excel/upload" : "/api/schema/upload";

  try {
    const res = await fetch(endpoint, { method: "POST", body: fd });
    const data = await res.json();

    if (!res.ok) {
      setError(data.detail ?? `Upload failed (${res.status})`);
      return;
    }

    if (data.no_schema_detected) {
      setNoSchemaDetected(true);
      return;
    }

    if (!data.upload_id) {
      setError("Backend did not return an upload_id.");
      return;
    }

    setUploadId(data.upload_id);
    setRaterName(data.rater_slug ?? "");
    setStep(2);
    pollWarmStatus(data.upload_id);
  } catch {
    setError("Upload failed. Is the backend running?");
  }
}
  // ── Step 2: Poll warm status ─────────────────────────────────────────────
 const intervalRef = useRef<NodeJS.Timeout | null>(null);

function pollWarmStatus(id: string) {
  if (intervalRef.current) clearInterval(intervalRef.current);
  
  intervalRef.current = setInterval(async () => {
    try {
      const res = await fetch(`/api/excel/warm-status/${id}`);
      const data = await res.json();
      setWarmStatus(data.status);

      if (data.status === "ready") {
        clearInterval(intervalRef.current!);
        intervalRef.current = null;
        setParsedConfig(data.parsed_config);
        const defaults: Record<string, any> = {};
        data.parsed_config?.inputs?.forEach((f: FieldDef) => {
          defaults[f.field] = f.default ?? "";
        });
        setTestInputs(defaults);
        setStep(3);
      }

      if (data.status === "error") {
        clearInterval(intervalRef.current!);
        intervalRef.current = null;
        setError(data.error_message ?? "Warm-up failed.");
        setStep(1);
      }
    } catch {
      clearInterval(intervalRef.current!);
      intervalRef.current = null;
      setError("Lost connection during warm-up.");
      setStep(1);
    }
  }, 1500);
}
  // ── Step 3: Test calculate ───────────────────────────────────────────────
  async function handleTestCalculate() {
    if (!parsedConfig) return;
    setTestLoading(true);
    setTestOutputs(null);
    setError("");

    const endpoint =
      engine === "excel" ? "/api/excel/test-calculate" : "/api/schema/calculate";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upload_id: uploadId, inputs: testInputs }),
      });
      const data = await res.json();
      setTestOutputs(data.outputs);
    } catch {
      setError("Test calculation failed.");
    } finally {
      setTestLoading(false);
    }
  }

  // ── Step 4: Save ─────────────────────────────────────────────────────────
  async function handleSave() {
    if (!parsedConfig) return;
    setSaving(true);
    setError("");

    try {
      const res = await fetch("/api/excel/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upload_id: uploadId,
          name: raterName,
          rater_type: raterType,
          config: parsedConfig,
        }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        setStep(4);
      } else {
        setError(data.detail ?? "Save failed.");
      }
    } catch {
      setError("Save failed.");
    } finally {
      setSaving(false);
    }
  }

  // ── No schema fallback handler ───────────────────────────────────────────
  function handleFallbackChoice(choice: "auto" | "switch" | "manual") {
    setNoSchemaDetected(false);
    if (choice === "switch") {
      setEngine("schema");
    } else if (choice === "auto") {
      // Re-upload with auto-generate flag
      handleUploadWithAutoSchema();
    }
    // "manual" — user will re-upload with schema sheet added
  }

  async function handleUploadWithAutoSchema() {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("auto_generate_schema", "true");

    try {
      const res = await fetch("/api/excel/upload", { method: "POST", body: fd });
      const data = await res.json();
      setUploadId(data.upload_id);
      setRaterName(data.rater_slug ?? "");
      setStep(2);
      pollWarmStatus(data.upload_id);
    } catch {
      setError("Auto-schema generation failed.");
    }
  }

  // ────────────────────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen bg-background p-8">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Upload Rater</h1>
            <p className="text-muted-foreground mt-1">
              Step {step} of 4
            </p>
          </div>
          <Link href="/admin">
            <Button variant="outline">← Dashboard</Button>
          </Link>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
            {error}
          </div>
        )}

        {/* No schema fallback */}
        {noSchemaDetected && (
          <NoSchemaFallback onChoice={handleFallbackChoice} />
        )}

        {/* ── STEP 1 ── */}
        {!noSchemaDetected && step === 1 && (
          <div className="space-y-6">
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-colors ${
                isDragActive
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              }`}
            >
              <input {...getInputProps()} />
              {file ? (
                <p className="font-medium">{file.name}</p>
              ) : (
                <>
                  <p className="text-lg font-medium">
                    Drop your .xlsx rater here
                  </p>
                  <p className="text-muted-foreground text-sm mt-1">
                    or click to browse
                  </p>
                </>
              )}
            </div>

            <EngineSelector selected={engine} onSelect={setEngine} />

            <Button
              className="w-full"
              disabled={!file || !engine}
              onClick={handleUpload}
            >
              Upload & Parse →
            </Button>
          </div>
        )}

        {/* ── STEP 2 ── */}
        {step === 2 && (
          <div className="text-center py-24 space-y-4">
            <div className="flex justify-center">
              <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
            <p className="text-lg font-medium">Warming up engine…</p>
            <p className="text-muted-foreground text-sm capitalize">
              Status: {warmStatus}
            </p>
          </div>
        )}

        {/* ── STEP 3 ── */}
        {step === 3 && parsedConfig && (
          <div className="space-y-6">
            {/* Rater name */}
            <div className="space-y-2">
              <Label>Rater Name</Label>
              <Input
                value={raterName}
                onChange={(e) => setRaterName(e.target.value)}
                placeholder="e.g. MPL Old Republic v2"
              />
            </div>

            <Separator />

            {/* Inputs preview */}
            <div>
              <h2 className="font-semibold mb-3">
                Inputs ({parsedConfig.inputs.length})
              </h2>
              <div className="space-y-2">
                {parsedConfig.inputs.map((f) => (
                  <div
                    key={f.field}
                    className="flex items-center justify-between p-3 rounded-lg border bg-card"
                  >
                    <div>
                      <p className="font-medium text-sm">{f.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {f.cell} · {f.type}
                        {f.group ? ` · ${f.group}` : ""}
                      </p>
                    </div>
                    <Input
                      className="w-40 text-sm"
                      value={testInputs[f.field] ?? ""}
                      onChange={(e) =>
                        setTestInputs((prev) => ({
                          ...prev,
                          [f.field]: e.target.value,
                        }))
                      }
                    />
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            {/* Outputs preview */}
            <div>
              <h2 className="font-semibold mb-3">
                Outputs ({parsedConfig.outputs.length})
              </h2>
              <div className="space-y-2">
                {parsedConfig.outputs.map((f) => (
                  <div
                    key={f.field}
                    className="flex items-center justify-between p-3 rounded-lg border bg-card"
                  >
                    <div>
                      <p className="font-medium text-sm">{f.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {f.cell} · {f.type}
                      </p>
                    </div>
                    {testOutputs && (
                      <Badge variant={f.primary ? "default" : "secondary"}>
                        {testOutputs[f.field] ?? "—"}
                      </Badge>
                    )}
                    {testLoading && (
                      <Skeleton className="h-6 w-20" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={handleTestCalculate}
                disabled={testLoading}
              >
                {testLoading ? "Calculating…" : "Test Calculate"}
              </Button>
              <Button
                className="flex-1"
                onClick={handleSave}
                disabled={saving || !raterName}
              >
                {saving ? "Saving…" : "Save Rater →"}
              </Button>
            </div>
          </div>
        )}

        {/* ── STEP 4 ── */}
        {step === 4 && (
          <div className="text-center py-24 space-y-4">
            <p className="text-5xl">✅</p>
            <h2 className="text-2xl font-bold">Rater Saved</h2>
            <p className="text-muted-foreground">
              {raterName} is now live and available to clients.
            </p>
            <div className="flex justify-center gap-3 pt-4">
              <Link href="/admin">
                <Button variant="outline">← Dashboard</Button>
              </Link>
              <Link href="/admin/upload">
                <Button onClick={() => { setStep(1); setFile(null); setEngine(null); }}>
                  Upload Another
                </Button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}