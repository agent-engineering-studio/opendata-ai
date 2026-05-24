import type { Resource } from "@/lib/types";
import { ResourceCard } from "./ResourceCard";

export function ResourceList({ resources }: { resources: Resource[] }) {
  if (resources.length === 0) return null;
  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Risorse trovate ({resources.length})
      </p>
      <div className="space-y-1.5">
        {resources.map((r, i) => (
          <ResourceCard key={`${r.url || r.name}-${i}`} resource={r} />
        ))}
      </div>
    </div>
  );
}
