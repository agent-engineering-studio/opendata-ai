"use client";

import Link from "next/link";

type Props = {
  onReset: () => void;
  canReset: boolean;
};

export function ChatHeader({ onReset, canReset }: Props) {
  return (
    <header className="flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-base font-semibold text-slate-900">
          OpenData AI
        </h1>
        <p className="text-xs text-slate-500">
          Il tuo agente di intelligenza artificiale per gli open data — portali
          CKAN e statistiche ufficiali (ISTAT, Eurostat, OCSE).
        </p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <nav className="flex gap-2 text-sm">
          <span className="rounded-md border border-blue-500 bg-blue-50 px-3 py-1 font-medium text-blue-800">
            Chat
          </span>
          <Link
            href="/mappa"
            className="rounded-md border border-slate-300 bg-white px-3 py-1 text-slate-700 hover:bg-slate-50"
          >
            Mappa
          </Link>
        </nav>
        <button
          type="button"
          onClick={onReset}
          disabled={!canReset}
          className="rounded-md border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
        >
          Nuova chat
        </button>
      </div>
    </header>
  );
}
