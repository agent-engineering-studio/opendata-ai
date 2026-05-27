"use client";

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
