import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";

interface FieldDef {
  field: string;
  type: string;
  label: string;
  description: string;
  group: string;
  options: string[];
  default: string | number | boolean | null | undefined;
}

interface Props {
  inputs: FieldDef[];
  values: Record<string, string | number | boolean | null | undefined>;
  onChange: (field: string, value: string | number | boolean | null | undefined) => void;
  errors?: Record<string, string | undefined>;
  warnings?: Record<string, string | undefined>;
}

export default function RatingForm({ inputs, values, onChange, errors, warnings }: Props) {
  // Group fields
  const groups: Record<string, FieldDef[]> = {};
  inputs.forEach((f) => {
    const g = f.group || "General";
    if (!groups[g]) groups[g] = [];
    groups[g].push(f);
  });

  return (
    <div className="space-y-6">
      {Object.entries(groups).map(([group, fields]) => (
        <div key={group}>
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            {group}
          </h3>
          <div className="space-y-4">
            {fields.map((f) => (
              <div key={f.field} className="space-y-1">
                <Label htmlFor={f.field}>
                  {f.label}
                  {f.description && (
                    <span className="ml-2 text-xs text-muted-foreground font-normal">
                      {f.description}
                    </span>
                  )}
                </Label>

                {f.type === "dropdown" && f.options?.length > 0 ? (
                  <Select
                    value={String(values[f.field] ?? "")}
                    onValueChange={(v) => onChange(f.field, v)}
                  >
                    <SelectTrigger id={f.field}>
                      <SelectValue placeholder="Select…" />
                    </SelectTrigger>
                    <SelectContent>
                      {f.options.map((opt) => (
                        <SelectItem key={String(opt)} value={String(opt)}>
                          {opt}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    id={f.field}
                    type={f.type === "number" ? "number" : "text"}
                    value={String(values[f.field] ?? "")}
                    onChange={(e) => onChange(f.field, e.target.value)}
                    placeholder={String(f.default ?? "")}
                  />
                )}

                {errors?.[f.field] && (
                  <p className="text-xs text-destructive">{errors[f.field]}</p>
                )}

                {!errors?.[f.field] && warnings?.[f.field] && (
                  <p className="text-xs text-muted-foreground">{warnings[f.field]}</p>
                )}
              </div>
            ))}
          </div>
          <Separator className="mt-6" />
        </div>
      ))}
    </div>
  );
}
