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
    // Chip compatte e fitte: occupano poco spazio verticale per lasciare
    // respiro alla chat (font + padding ridotti, gap stretto).
    <div className="flex flex-wrap gap-1">
      {EXAMPLE_QUERIES.map((ex) => (
        <Chip
          key={ex.label}
          tag="button"
          simple
          color={sourceChipColor(ex.source)}
          onClick={() => onPick(ex.query)}
          disabled={disabled}
          className="cursor-pointer"
          style={{ height: "auto", padding: "1px 9px", fontSize: "0.72rem", lineHeight: 1.5 }}
          {...({ type: "button" } as Record<string, unknown>)}
        >
          {ex.source ? (
            <span className="me-1 text-[8.5px] font-semibold uppercase tracking-wide opacity-70">
              {sourceLabel(ex.source)}
            </span>
          ) : null}
          <ChipLabel style={{ fontSize: "0.72rem", margin: 0 }}>{ex.label}</ChipLabel>
        </Chip>
      ))}
    </div>
  );
}
