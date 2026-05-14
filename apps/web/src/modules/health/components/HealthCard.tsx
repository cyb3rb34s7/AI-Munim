import { Card, Loader } from '@/shared/components';

import type { HealthData } from '../types/health.types';

interface HealthCardProps {
  loading: boolean;
  error: Error | null;
  health: HealthData | undefined;
  traceId: string | undefined;
}

/**
 * Pure presentational component (docs/conventions.md §12.4). All data + state
 * are passed in as props by the connector in HealthSection.tsx.
 */
export function HealthCard({ loading, error, health, traceId }: HealthCardProps) {
  return (
    <Card
      title="API health"
      trailing={
        traceId ? (
          <span className="font-mono text-xs text-fg-muted" title="trace_id">
            {traceId}
          </span>
        ) : null
      }
    >
      {loading && <Loader label="Checking…" size="sm" />}

      {error && (
        <div className="text-destructive">
          <p className="font-medium">Unreachable</p>
          <p className="mt-1 font-mono text-xs">{error.message}</p>
        </div>
      )}

      {!loading && !error && health && (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-fg-muted">Status</dt>
          <dd className="font-medium text-success">{health.status}</dd>

          <dt className="text-fg-muted">Version</dt>
          <dd className="font-mono">{health.version}</dd>
        </dl>
      )}
    </Card>
  );
}
