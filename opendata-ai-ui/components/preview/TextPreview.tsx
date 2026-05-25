export function TextPreview({ content }: { content: string }) {
  return (
    <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-3 font-mono text-xs break-words whitespace-pre-wrap text-slate-800">
      {content}
    </pre>
  );
}
