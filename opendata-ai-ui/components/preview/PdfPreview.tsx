"use client";

export function PdfPreview({ url }: { url: string }) {
  return (
    <div className="overflow-hidden rounded border border-slate-200">
      <iframe
        src={url}
        title="Anteprima PDF"
        className="block h-[28rem] w-full bg-slate-50"
      />
    </div>
  );
}
