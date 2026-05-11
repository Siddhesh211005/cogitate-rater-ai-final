import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface FieldDef {
  field: string;
  label: string;
  type: string;
  primary: boolean;
}

interface Props {
  outputs: FieldDef[];
  values: Record<string, string | number | boolean | null | undefined>;
  downloadUrl?: string | null;
}

function formatValue(value: string | number | boolean | null | undefined, type: string): string {
  if (value === null || value === undefined) return "—";
  if (type === "number" && typeof value === "number") {
    return value.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return String(value);
}

export default function ResultsDashboard({ outputs, values, downloadUrl }: Props) {
  const primary = outputs.filter((f) => f.primary);
  const secondary = outputs.filter((f) => !f.primary);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Results</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Primary outputs — large display */}
        {primary.map((f) => (
          <div key={f.field} className="text-center py-4">
            <p className="text-sm text-muted-foreground">{f.label}</p>
            <p className="text-4xl font-bold mt-1">
              {formatValue(values[f.field], f.type)}
            </p>
          </div>
        ))}

        {primary.length > 0 && secondary.length > 0 && (
          <Separator />
        )}

        {/* Secondary outputs */}
        {secondary.map((f) => (
          <div key={f.field} className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">{f.label}</span>
            <Badge variant="secondary">
              {formatValue(values[f.field], f.type)}
            </Badge>
          </div>
        ))}

        {/* Download */}
        {downloadUrl && (
          <>
            <Separator />
            <a href={downloadUrl} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" className="w-full">
                ⬇ Download Calculated Workbook
              </Button>
            </a>
          </>
        )}
      </CardContent>
    </Card>
  );
}
