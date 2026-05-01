import { Button } from "@/components/ui/button";

interface Props {
  selected: "excel" | "schema" | null;
  onSelect: (engine: "excel" | "schema") => void;
}

export default function EngineSelector({ selected, onSelect }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Select Engine</p>
      <div className="flex gap-3">
        <Button
          variant={selected === "schema" ? "default" : "outline"}
          className="flex-1 h-16 flex-col"
          onClick={() => onSelect("schema")}
        >
          <span className="font-semibold">Schema Engine</span>
          <span className="text-xs font-normal opacity-70">
            Python formulas · no _Schema sheet needed
          </span>
        </Button>
        <Button
          variant={selected === "excel" ? "default" : "outline"}
          className="flex-1 h-16 flex-col"
          onClick={() => onSelect("excel")}
        >
          <span className="font-semibold">Excel Engine</span>
          <span className="text-xs font-normal opacity-70">
            Native COM · requires _Schema sheet
          </span>
        </Button>
      </div>
    </div>
  );
}