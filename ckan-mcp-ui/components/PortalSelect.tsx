"use client";

import { useState } from "react";
import {
  PORTAL_PRESETS,
  CUSTOM_PORTAL_VALUE,
  DEFAULT_PORTAL,
} from "@/lib/portals";

type Props = {
  value: string;
  onChange: (url: string) => void;
};

export function PortalSelect({ value, onChange }: Props) {
  const isPreset = PORTAL_PRESETS.some((p) => p.url === value);
  const [mode, setMode] = useState<"preset" | "custom">(
    isPreset || value === "" ? "preset" : "custom",
  );

  function handleSelectChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value;
    if (next === CUSTOM_PORTAL_VALUE) {
      setMode("custom");
      onChange("");
    } else {
      setMode("preset");
      onChange(next);
    }
  }

  const selectValue =
    mode === "custom" ? CUSTOM_PORTAL_VALUE : value || DEFAULT_PORTAL;

  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
      <label className="text-xs font-medium uppercase tracking-wide text-slate-500 sm:text-sm sm:normal-case sm:tracking-normal sm:text-slate-600">
        Portale
      </label>
      <select
        value={selectValue}
        onChange={handleSelectChange}
        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        {PORTAL_PRESETS.map((p) => (
          <option key={p.url} value={p.url}>
            {p.label}
          </option>
        ))}
        <option value={CUSTOM_PORTAL_VALUE}>Personalizzato…</option>
      </select>
      {mode === "custom" ? (
        <input
          type="url"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="https://..."
          className="flex-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      ) : null}
    </div>
  );
}
