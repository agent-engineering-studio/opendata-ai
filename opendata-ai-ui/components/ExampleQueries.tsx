"use client";

import { Chip, ChipLabel } from "design-react-kit";
import { EXAMPLE_QUERIES, type ExampleQuery } from "@/lib/examples";

type Props = {
  onPick: (query: string) => void;
  disabled: boolean;
};

function sourceChipColor(source: ExampleQuery["source"]): string {
  if (source === "ckan") return "primary";
  if (source === "istat") return "warning";
  if (source === "eurostat") return "secondary";
  if (source === "oecd") return "danger";
  if (source === "cross") return "success";
  return "primary";
}

function sourceLabel(source: ExampleQuery["source"]): string {
  if (source === "cross") return "multi";
  return source ?? "";
}

export function ExampleQueries({ onPick, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {EXAMPLE_QUERIES.map((ex) => (
        <Chip
          key={ex.label}
          tag="button"
          simple
          color={sourceChipColor(ex.source)}
          onClick={() => onPick(ex.query)}
          disabled={disabled}
          className="cursor-pointer"
          {...({ type: "button" } as Record<string, unknown>)}
        >
          {ex.source ? (
            <span className="me-2 text-[10px] font-semibold uppercase tracking-wide">
              {sourceLabel(ex.source)}
            </span>
          ) : null}
          <ChipLabel>{ex.label}</ChipLabel>
        </Chip>
      ))}
    </div>
  );
}
