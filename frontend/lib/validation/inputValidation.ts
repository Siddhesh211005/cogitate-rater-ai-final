export interface ValidationFieldDef {
  field: string;
  type?: string;
  label?: string;
  description?: string;
  min?: number;
  max?: number;
}

export interface ValidationResult {
  error?: string;
  warning?: string;
}

const NUMERIC_HINTS = [
  "year",
  "limit",
  "premium",
  "deductible",
  "amount",
  "factor",
  "surcharge",
  "rate",
  "score",
  "value",
  "cost",
  "age",
  "construction",
];

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string" && value.trim() === "") return true;
  return false;
}

function isNumericValue(value: unknown): boolean {
  if (typeof value === "number" && Number.isFinite(value)) return true;
  if (typeof value !== "string") return false;
  const cleaned = value.trim().replace(/,/g, "");
  if (cleaned === "") return false;
  return !Number.isNaN(Number(cleaned));
}

function hasNumericHint(text: string): boolean {
  const lowered = text.toLowerCase();
  return NUMERIC_HINTS.some((hint) => lowered.includes(hint));
}

function getDisplayName(field: ValidationFieldDef): string {
  return field.label || field.field;
}

function isNumericField(field: ValidationFieldDef): boolean {
  if (field.type && ["number", "int", "integer", "float"].includes(field.type.toLowerCase())) {
    return true;
  }
  if (hasNumericHint(field.field)) return true;
  if (field.label && hasNumericHint(field.label)) return true;
  if (field.description && hasNumericHint(field.description)) return true;
  return false;
}

function isPlaceholder(value: unknown, field: ValidationFieldDef): boolean {
  if (typeof value !== "string" || !field.label) return false;
  return value.trim().toLowerCase() === field.label.trim().toLowerCase();
}

export function validateFieldValue(
  field: ValidationFieldDef,
  value: unknown
): ValidationResult {
  const displayName = getDisplayName(field);

  if (isEmptyValue(value)) {
    return { error: `${displayName} cannot be empty` };
  }

  const numericField = isNumericField(field);
  if (numericField && isPlaceholder(value, field)) {
    return { error: `${displayName} must be numeric` };
  }

  if (numericField && !isNumericValue(value)) {
    return { error: `${displayName} must be numeric` };
  }

  if (numericField && isNumericValue(value)) {
    const numericValue = typeof value === "number" ? value : Number(String(value).replace(/,/g, ""));
    if (field.min !== undefined && numericValue < field.min) {
      return { warning: `${displayName} is below the recommended minimum` };
    }
    if (field.max !== undefined && numericValue > field.max) {
      return { warning: `${displayName} is above the recommended maximum` };
    }
  }

  return {};
}
