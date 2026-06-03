"use client";

import { Button } from "design-react-kit";

type Props = {
  onReset: () => void;
  canReset: boolean;
};

// Per-chat actions only. Site branding + navigation live in <SiteHeader>.
export function ChatHeader({ onReset, canReset }: Props) {
  return (
    <div className="flex items-center justify-end border-b border-[var(--color-border)] bg-white px-4 py-2">
      <Button
        color="primary"
        outline
        size="xs"
        onClick={onReset}
        disabled={!canReset}
      >
        Nuova chat
      </Button>
    </div>
  );
}
