import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  onChoice: (choice: "auto" | "switch" | "manual") => void;
}

export default function NoSchemaFallback({ onChoice }: Props) {
  return (
    <Card className="border-yellow-500/50 bg-yellow-500/5">
      <CardHeader>
        <CardTitle className="text-lg">
          ⚠️ No <code className="text-sm">_Schema</code> sheet detected
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          The Excel engine requires a <code>_Schema</code> sheet. Choose how to
          proceed:
        </p>
        <Button className="w-full" onClick={() => onChoice("auto")}>
          Auto-generate Schema
          <span className="ml-2 text-xs opacity-70">
            — scan workbook and generate _Schema automatically
          </span>
        </Button>
        <Button
          variant="outline"
          className="w-full"
          onClick={() => onChoice("switch")}
        >
          Switch to Schema Engine
          <span className="ml-2 text-xs opacity-70">
            — no _Schema sheet required
          </span>
        </Button>
        <Button
          variant="outline"
          className="w-full"
          onClick={() => onChoice("manual")}
        >
          Upload _Schema manually
          <span className="ml-2 text-xs opacity-70">
            — add the sheet yourself and re-upload
          </span>
        </Button>
      </CardContent>
    </Card>
  );
}