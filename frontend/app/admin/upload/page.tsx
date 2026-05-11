"use client";

import { useCallback, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import EngineSelector from "@/components/EngineSelector";
import NoSchemaFallback from "@/components/NoSchemaFallback";

type Engine = "excel" | "schema";
type Step = 1 | 2 | 3 | 4;
type FieldValue = string | number | boolean | null | undefined;

interface FieldDef {
  field: string;
  cell: string;
  type: string;
  label: string;
  description?: string;
  group?: string;
  options?: string[];
  default?: FieldValue;
  direction?: string;
  primary?: boolean;
}

interface ParsedConfig {
  slug?: string;
  name?: string;
  sheet: string;
  inputs: FieldDef[];
  outputs: FieldDef[];
}

interface NoSchemaUpload {
  upload_id: string;
  filepath: string;
}

function slugify(value: string) {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "uploaded-rater"
  );
}

function defaultsFromConfig(config: ParsedConfig) {
  const defaults: Record<string, FieldValue> = {};
  config.inputs?.forEach((field) => {
    defaults[field.field] = field.default ?? "";
  });
  return defaults;
}

export default function UploadPage() {
  const [step, setStep] = useState<Step>(1);
  const [engine, setEngine] = useState<Engine | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState("");
  const [warmStatus, setWarmStatus] = useState("");
  const [parsedConfig, setParsedConfig] = useState<ParsedConfig | null>(null);
  const [raterName, setRaterName] = useState("");
  const [raterType] = useState("custom");
  const [testInputs, setTestInputs] = useState<Record<string, FieldValue>>({});
  const [testOutputs, setTestOutputs] = useState<Record<string, FieldValue> | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [noSchemaDetected, setNoSchemaDetected] = useState(false);
  const [noSchemaUpload, setNoSchemaUpload] = useState<NoSchemaUpload | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) {
      setFile(accepted[0]);
      if (!raterName) setRaterName(accepted[0].name.replace(/\.xlsx?$/i, ""));
    }
  }, [raterName]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    },
    maxFiles: 1,
  });

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
          const config = data.parsed_config ?? data.config;
          setParsedConfig(config);
          setTestInputs(defaultsFromConfig(config));
          setStep(3);
        }

        if (data.status === "failed" || data.status === "error") {
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

  async function handleUpload() {
    if (!file || !engine) return;
    setError("");

    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", raterName || file.name.replace(/\.xlsx?$/i, ""));
    fd.append("rater_type", raterType);

    const endpoint = engine === "excel" ? "/api/excel/upload" : "/api/schema/upload";

    try {
      const res = await fetch(endpoint, { method: "POST", body: fd });
      const data = await res.json();

      if (!res.ok) {
        setError(data.detail ?? `Upload failed (${res.status})`);
        return;
      }

      if (data.no_schema_detected) {
        setNoSchemaUpload({ upload_id: data.upload_id, filepath: data.filepath });
        setNoSchemaDetected(true);
        return;
      }

      if (!data.upload_id) {
        setError("Backend did not return an upload_id.");
        return;
      }

      setUploadId(data.upload_id);
      setRaterName(raterName || file.name.replace(/\.xlsx?$/i, ""));

      if (engine === "excel") {
        setStep(2);
        pollWarmStatus(data.upload_id);
      } else {
        const config = data.parsed_config ?? data.config;
        setParsedConfig(config);
        setTestInputs(defaultsFromConfig(config));
        setStep(3);
      }
    } catch {
      setError("Upload failed. Is the backend running?");
    }
  }

  async function handleTestCalculate() {
    if (!parsedConfig) return;
    if (engine !== "excel") {
      setError("Schema-engine upload testing is not wired here yet. Save it, then test from the client panel.");
      return;
    }

    setTestLoading(true);
    setTestOutputs(null);
    setError("");

    try {
      const res = await fetch("/api/excel/test-calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upload_id: uploadId, inputs: testInputs }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail ?? "Test calculation failed.");
        return;
      }
      setTestOutputs(data.outputs);
    } catch {
      setError("Test calculation failed.");
    } finally {
      setTestLoading(false);
    }
  }

  async function handleTestDownload() {
    if (!parsedConfig || engine !== "excel") return;
    setDownloadLoading(true);
    setError("");

    try {
      const res = await fetch("/api/excel/test-download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upload_id: uploadId, inputs: testInputs }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail ?? "Download failed.");
        return;
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${slugify(raterName || "test")}_calculated.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError("Download failed.");
    } finally {
      setDownloadLoading(false);
    }
  }

  async function handleSave() {
    if (!parsedConfig) return;
    setSaving(true);
    setError("");

    const slug = slugify(raterName || parsedConfig.name || "uploaded-rater");
    const endpoint = engine === "excel" ? "/api/excel/save" : "/api/schema/save";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upload_id: uploadId,
          slug,
          name: raterName || slug,
          rater_type: raterType,
          config: { ...parsedConfig, slug, name: raterName || slug },
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

  async function handleFallbackChoice(choice: "auto" | "switch" | "manual") {
    setNoSchemaDetected(false);
    if (choice === "manual") return;
    if (!noSchemaUpload) {
      setError("Missing uploaded workbook reference. Please re-upload.");
      return;
    }

    try {
      const res = await fetch("/api/excel/handle-no-schema", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          option: choice === "auto" ? "auto_generate" : "switch_to_schema",
          upload_id: noSchemaUpload.upload_id,
          filepath: noSchemaUpload.filepath,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail ?? "Fallback failed.");
        return;
      }
      setUploadId(noSchemaUpload.upload_id);
      setEngine(choice === "switch" ? "schema" : "excel");
      if (choice === "auto") {
        setStep(2);
        pollWarmStatus(noSchemaUpload.upload_id);
      } else {
        setParsedConfig(data.config);
        setTestInputs(defaultsFromConfig(data.config));
        setStep(3);
      }
    } catch {
      setError("Fallback failed.");
    }
  }

  return (
    <main className="min-h-screen bg-background p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Upload Rater</h1>
            <p className="text-muted-foreground mt-1">Step {step} of 4</p>
          </div>
          <Link href="/admin">
            <Button variant="outline">Back to Dashboard</Button>
          </Link>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
            {error}
          </div>
        )}

        {noSchemaDetected && <NoSchemaFallback onChoice={handleFallbackChoice} />}

        {!noSchemaDetected && step === 1 && (
          <div className="space-y-6">
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-colors ${
                isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
              }`}
            >
              <input {...getInputProps()} />
              {file ? (
                <p className="font-medium">{file.name}</p>
              ) : (
                <>
                  <p className="text-lg font-medium">Drop your .xlsx rater here</p>
                  <p className="text-muted-foreground text-sm mt-1">or click to browse</p>
                </>
              )}
            </div>

            <EngineSelector selected={engine} onSelect={setEngine} />

            <Button className="w-full" disabled={!file || !engine} onClick={handleUpload}>
              Upload & Parse
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="text-center py-24 space-y-4">
            <div className="flex justify-center">
              <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
            <p className="text-lg font-medium">Warming up Excel engine...</p>
            <p className="text-muted-foreground text-sm capitalize">Status: {warmStatus}</p>
          </div>
        )}

        {step === 3 && parsedConfig && (
          <div className="space-y-6">
            <div className="space-y-2">
              <Label>Rater Name</Label>
              <Input
                value={raterName}
                onChange={(event) => setRaterName(event.target.value)}
                placeholder="e.g. MPL Old Republic v2"
              />
            </div>

            <Separator />

            <div>
              <h2 className="font-semibold mb-3">Inputs ({parsedConfig.inputs.length})</h2>
              <div className="space-y-2">
                {parsedConfig.inputs.map((field) => (
                  <div key={field.field} className="flex items-center justify-between p-3 rounded-lg border bg-card">
                    <div>
                      <p className="font-medium text-sm">{field.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {field.cell} - {field.type}
                        {field.group ? ` - ${field.group}` : ""}
                      </p>
                    </div>
                    <Input
                      className="w-40 text-sm"
                      value={String(testInputs[field.field] ?? "")}
                      onChange={(event) =>
                        setTestInputs((prev) => ({ ...prev, [field.field]: event.target.value }))
                      }
                    />
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            <div>
              <h2 className="font-semibold mb-3">Outputs ({parsedConfig.outputs.length})</h2>
              <div className="space-y-2">
                {parsedConfig.outputs.map((field) => (
                  <div key={field.field} className="flex items-center justify-between p-3 rounded-lg border bg-card">
                    <div>
                      <p className="font-medium text-sm">{field.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {field.cell} - {field.type}
                      </p>
                    </div>
                    {testOutputs && (
                      <Badge variant={field.primary ? "default" : "secondary"}>
                        {testOutputs[field.field] ?? "-"}
                      </Badge>
                    )}
                    {testLoading && <Skeleton className="h-6 w-20" />}
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button variant="outline" className="flex-1" onClick={handleTestCalculate} disabled={testLoading}>
                {testLoading ? "Calculating..." : "Test Calculate"}
              </Button>
              {engine === "excel" && (
                <Button variant="outline" className="flex-1" onClick={handleTestDownload} disabled={downloadLoading}>
                  {downloadLoading ? "Downloading..." : "Test Download"}
                </Button>
              )}
              <Button className="flex-1" onClick={handleSave} disabled={saving || !raterName}>
                {saving ? "Saving..." : "Save Rater"}
              </Button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="text-center py-24 space-y-4">
            <h2 className="text-2xl font-bold">Rater Saved</h2>
            <p className="text-muted-foreground">{raterName} is now live and available to clients.</p>
            <div className="flex justify-center gap-3 pt-4">
              <Link href="/admin">
                <Button variant="outline">Dashboard</Button>
              </Link>
              <Button
                onClick={() => {
                  setStep(1);
                  setFile(null);
                  setEngine(null);
                  setParsedConfig(null);
                }}
              >
                Upload Another
              </Button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
