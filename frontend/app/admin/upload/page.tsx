"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  sheet?: string;
  inputs: FieldDef[];
  outputs: FieldDef[];
}

interface NoSchemaUpload {
  upload_id: string;
  filepath: string;
}

function slugify(value: string): string {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "uploaded-rater";
}

function defaultsFromConfig(config: ParsedConfig): Record<string, FieldValue> {
  const defaults: Record<string, FieldValue> = {};
  (config.inputs ?? []).forEach((field) => {
    defaults[field.field] = field.default ?? "";
  });
  return defaults;
}

function formatOutputValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (
    typeof value === "string" &&
    ["", "empty", "none", "null"].includes(value.trim().toLowerCase())
  ) {
    return "-";
  }
  return String(value);
}

export default function UploadPage() {
  const [step, setStep] = useState<Step>(1);
  const [engine, setEngine] = useState<Engine | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState("");
  const [warmStatus, setWarmStatus] = useState("");
  const [parsedConfig, setParsedConfig] = useState<ParsedConfig | null>(null);
  const [raterName, setRaterName] = useState("");
  const [testInputs, setTestInputs] = useState<Record<string, FieldValue>>({});
  const [testOutputs, setTestOutputs] = useState<Record<string, FieldValue> | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [noSchemaDetected, setNoSchemaDetected] = useState(false);
  const [noSchemaUpload, setNoSchemaUpload] = useState<NoSchemaUpload | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const raterType = "custom";

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (!accepted[0]) return;
      setFile(accepted[0]);
      if (!raterName.trim()) {
        setRaterName(accepted[0].name.replace(/\.xlsx?$/i, ""));
      }
    },
    [raterName]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx", ".xlsm", ".xls"],
    },
    maxFiles: 1,
  });

  function stopPolling() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  function pollWarmStatus(id: string, targetEngine: Engine) {
    stopPolling();

    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/${targetEngine}/warm-status/${id}`);
        const data = await res.json();
        if (!res.ok) {
          throw new Error(
            typeof data.detail === "string" ? data.detail : "Warm-up failed."
          );
        }

        const status = data?.session?.status ?? data?.status ?? "waiting";
        const config = data?.session?.config ?? data?.parsed_config ?? data?.config;
        setWarmStatus(status);

        if (status === "ready" || status === "parsed") {
          stopPolling();
          if (!config) {
            throw new Error("Warm status did not include parsed config.");
          }
          setParsedConfig(config);
          setTestInputs(defaultsFromConfig(config));
          setStep(3);
        }

        if (status === "failed" || status === "error") {
          stopPolling();
          setError(data.error_message ?? "Warm-up failed.");
          setStep(1);
        }
      } catch (err) {
        stopPolling();
        setError(err instanceof Error ? err.message : "Lost connection during warm-up.");
        setStep(1);
      }
    }, 1500);
  }

  async function handleUpload() {
    if (!file || !engine) return;
    if (!raterName.trim()) {
      setError("Please enter a rater name before uploading.");
      return;
    }

    setError("");
    setTestOutputs(null);
    setNoSchemaDetected(false);

    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", raterName.trim());
    fd.append("rater_type", raterType);

    const endpoint = engine === "excel" ? "/api/excel/upload" : "/api/schema/upload";

    try {
      const res = await fetch(endpoint, { method: "POST", body: fd });
      const data = await res.json();

      if (!res.ok) {
        const msg =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
            ? data.detail.map((e: { msg?: string }) => e.msg).filter(Boolean).join(", ")
            : `Upload failed (${res.status})`;
        setError(msg);
        return;
      }

      if (data.status === "no_schema" || data.no_schema_detected) {
        if (data.upload_id && data.filepath) {
          setNoSchemaUpload({ upload_id: data.upload_id, filepath: data.filepath });
        }
        setNoSchemaDetected(true);
        return;
      }

      if (!data.upload_id) {
        setError("Backend did not return an upload_id.");
        return;
      }

      const config = data.config ?? data.parsed_config;
      setUploadId(data.upload_id);

      if (engine === "excel") {
        setWarmStatus(data.warm_status ?? "warming");
        setStep(2);
        pollWarmStatus(data.upload_id, "excel");
        return;
      }

      if (!config) {
        setError("Backend did not return parsed config.");
        return;
      }

      setParsedConfig(config);
      setTestInputs(defaultsFromConfig(config));
      setStep(3);
    } catch {
      setError("Upload failed. Is the backend running?");
    }
  }

  async function handleTestCalculate() {
    if (!parsedConfig || !engine || !uploadId) return;

    setTestLoading(true);
    setTestOutputs(null);
    setError("");

    const endpoint =
      engine === "excel" ? "/api/excel/test-calculate" : "/api/schema/test-calculate";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upload_id: uploadId, inputs: testInputs }),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg =
          typeof data.detail === "string"
            ? data.detail
            : `Test calculation failed (${res.status})`;
        setError(msg);
        return;
      }
      setTestOutputs(data.outputs ?? null);
    } catch {
      setError("Test calculation failed.");
    } finally {
      setTestLoading(false);
    }
  }

  async function handleTestDownload() {
    if (!parsedConfig || engine !== "excel" || !uploadId) return;

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
        setError(
          typeof data.detail === "string" ? data.detail : "Download failed."
        );
        return;
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${slugify(raterName || parsedConfig.name || "test")}_calculated.xlsx`;
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
    if (!parsedConfig || !engine || !uploadId) return;

    setSaving(true);
    setError("");

    const normalizedName = raterName.trim() || parsedConfig.name || "uploaded-rater";
    const slug = slugify(normalizedName);
    const endpoint = engine === "excel" ? "/api/excel/save" : "/api/schema/save";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upload_id: uploadId,
          name: normalizedName,
          slug,
          rater_type: raterType,
          config: { ...parsedConfig, slug, name: normalizedName },
        }),
      });
      const data = await res.json();

      if (res.ok && data.status === "ok") {
        setStep(4);
      } else {
        const msg =
          typeof data.detail === "string"
            ? data.detail
            : `Save failed (${res.status})`;
        setError(msg);
      }
    } catch {
      setError("Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleFallbackChoice(choice: "auto" | "switch" | "manual") {
    setNoSchemaDetected(false);

    if (choice === "manual") {
      setStep(1);
      return;
    }

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
        setError(
          typeof data.detail === "string" ? data.detail : "Fallback failed."
        );
        return;
      }

      const nextUploadId = data.upload_id ?? noSchemaUpload.upload_id;
      const nextEngine: Engine = choice === "switch" ? "schema" : "excel";
      setUploadId(nextUploadId);
      setEngine(nextEngine);

      if (choice === "auto") {
        setStep(2);
        setWarmStatus(data.warm_status ?? "warming");
        pollWarmStatus(nextUploadId, "excel");
        return;
      }

      const config = data.config;
      if (!config) {
        setError("Fallback response did not include parsed config.");
        return;
      }

      setParsedConfig(config);
      setTestInputs(defaultsFromConfig(config));
      setStep(3);
    } catch {
      setError("Fallback failed.");
    }
  }

  return (
    <main className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Upload Rater</h1>
            <p className="mt-1 text-muted-foreground">Step {step} of 4</p>
          </div>
          <Link href="/admin">
            <Button variant="outline">Back to Dashboard</Button>
          </Link>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {noSchemaDetected && <NoSchemaFallback onChoice={handleFallbackChoice} />}

        {!noSchemaDetected && step === 1 && (
          <div className="space-y-6">
            <div className="space-y-2">
              <Label>Rater Name *</Label>
              <Input
                value={raterName}
                onChange={(event) => setRaterName(event.target.value)}
                placeholder="e.g. MPL Old Republic v2"
              />
            </div>

            <div
              {...getRootProps()}
              className={`cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-colors ${
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
                  <p className="text-lg font-medium">Drop your .xlsx rater here</p>
                  <p className="mt-1 text-sm text-muted-foreground">or click to browse</p>
                </>
              )}
            </div>

            <EngineSelector selected={engine} onSelect={setEngine} />

            <Button
              className="w-full"
              disabled={!file || !engine || !raterName.trim()}
              onClick={handleUpload}
            >
              Upload & Parse
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 py-24 text-center">
            <div className="flex justify-center">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
            <p className="text-lg font-medium">Warming up Excel engine...</p>
            <p className="text-sm capitalize text-muted-foreground">Status: {warmStatus}</p>
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
              <h2 className="mb-3 font-semibold">
                Inputs ({(parsedConfig.inputs ?? []).length})
              </h2>
              <div className="space-y-2">
                {(parsedConfig.inputs ?? []).map((field) => (
                  <div
                    key={field.field}
                    className="flex items-center justify-between rounded-lg border bg-card p-3"
                  >
                    <div>
                      <p className="text-sm font-medium">{field.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {field.cell} - {field.type}
                        {field.group ? ` - ${field.group}` : ""}
                      </p>
                    </div>
                    {field.type === "dropdown" && (field.options?.length ?? 0) > 0 ? (
                      <Select
                        value={
                          testInputs[field.field] === undefined ||
                          testInputs[field.field] === null ||
                          testInputs[field.field] === ""
                            ? undefined
                            : String(testInputs[field.field])
                        }
                        onValueChange={(value) =>
                          setTestInputs((prev) => ({ ...prev, [field.field]: value }))
                        }
                      >
                        <SelectTrigger className="w-40 text-sm">
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                        <SelectContent>
                          {field.options?.map((option) => (
                            <SelectItem key={`${field.field}-${option}`} value={String(option)}>
                              {option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input
                        className="w-40 text-sm"
                        value={String(testInputs[field.field] ?? "")}
                        onChange={(event) =>
                          setTestInputs((prev) => ({
                            ...prev,
                            [field.field]: event.target.value,
                          }))
                        }
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            <div>
              <h2 className="mb-3 font-semibold">
                Outputs ({(parsedConfig.outputs ?? []).length})
              </h2>
              <div className="space-y-2">
                {(parsedConfig.outputs ?? []).map((field) => (
                  <div
                    key={field.field}
                    className="flex items-center justify-between rounded-lg border bg-card p-3"
                  >
                    <div>
                      <p className="text-sm font-medium">{field.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {field.cell} - {field.type}
                      </p>
                    </div>
                    {testOutputs && (
                      <Badge variant={field.primary ? "default" : "secondary"}>
                        {formatOutputValue(testOutputs[field.field])}
                      </Badge>
                    )}
                    {testLoading && <Skeleton className="h-6 w-20" />}
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={handleTestCalculate}
                disabled={testLoading}
              >
                {testLoading ? "Calculating..." : "Test Calculate"}
              </Button>
              {engine === "excel" && (
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={handleTestDownload}
                  disabled={downloadLoading}
                >
                  {downloadLoading ? "Downloading..." : "Test Download"}
                </Button>
              )}
              <Button
                className="flex-1"
                onClick={handleSave}
                disabled={saving || !raterName.trim()}
              >
                {saving ? "Saving..." : "Save Rater"}
              </Button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4 py-24 text-center">
            <h2 className="text-2xl font-bold">Rater Saved</h2>
            <p className="text-muted-foreground">
              {raterName} is now live and available to clients.
            </p>
            <div className="flex justify-center gap-3 pt-4">
              <Link href="/admin">
                <Button variant="outline">Dashboard</Button>
              </Link>
              <Button
                onClick={() => {
                  stopPolling();
                  setStep(1);
                  setEngine(null);
                  setFile(null);
                  setUploadId("");
                  setWarmStatus("");
                  setParsedConfig(null);
                  setTestInputs({});
                  setTestOutputs(null);
                  setError("");
                  setNoSchemaDetected(false);
                  setNoSchemaUpload(null);
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
