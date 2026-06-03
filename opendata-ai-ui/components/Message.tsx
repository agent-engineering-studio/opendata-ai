import type { ChatMessage } from "@/lib/types";
import { AssistantMarkdown } from "./AssistantMarkdown";
import { ResourceList } from "./ResourceList";

function Paragraphs({ text }: { text: string }) {
  const blocks = text
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean);
  if (blocks.length === 0) return null;
  return (
    <div className="space-y-2">
      {blocks.map((block, i) => (
        <p key={i} className="whitespace-pre-wrap leading-relaxed">
          {block}
        </p>
      ))}
    </div>
  );
}

export function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-[var(--color-primary)] px-4 py-2 text-white">
          <Paragraphs text={message.text} />
        </div>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div className="flex justify-start">
        <div
          role="alert"
          className="alert alert-danger max-w-[80%] mb-0"
        >
          <Paragraphs text={message.text} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-2xl rounded-bl-sm border border-[var(--color-border)] bg-white px-4 py-3 text-[var(--color-text)] shadow-sm">
        <AssistantMarkdown text={message.text} />
        <ResourceList resources={message.resources} />
        <div className="mt-3 text-xs text-[var(--color-text-muted)]">
          ⏱ {(message.durationMs / 1000).toFixed(1)}s
        </div>
      </div>
    </div>
  );
}
