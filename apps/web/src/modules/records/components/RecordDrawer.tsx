import { Button, Loader } from '@/shared/components';

import type { RecordDetail } from '../types/record.types';

interface RecordDrawerProps {
  record: RecordDetail | undefined;
  isLoading: boolean;
  error: Error | null;
  onClose: () => void;
}

export function RecordDrawer({ record, isLoading, error, onClose }: RecordDrawerProps) {
  return (
    <aside className="fixed inset-y-0 right-0 w-[600px] max-w-[90vw] overflow-y-auto border-l border-border bg-bg shadow-xl">
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <div>
          <h3 className="text-base font-semibold">Record detail</h3>
          {record && (
            <p className="font-mono text-xs text-muted">
              {record.source_system} · {record.source_id}
            </p>
          )}
        </div>
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      </header>
      <div className="space-y-6 px-6 py-4">
        {isLoading && <Loader label="Loading record…" />}
        {error && <p className="text-sm text-error">{error.message}</p>}
        {record && (
          <>
            <section>
              <h4 className="text-xs font-semibold uppercase text-muted">Normalized</h4>
              <pre className="mt-2 overflow-x-auto rounded-md bg-bg-subtle p-3 text-xs">
                {JSON.stringify(record.normalized, null, 2)}
              </pre>
            </section>
            <section>
              <h4 className="text-xs font-semibold uppercase text-muted">
                Raw (provenance — exact Shopify payload)
              </h4>
              <pre className="mt-2 overflow-x-auto rounded-md bg-bg-subtle p-3 text-xs">
                {JSON.stringify(record.raw, null, 2)}
              </pre>
            </section>
            <section className="text-xs text-muted">
              <p>
                <span className="font-mono">payload_hash:</span> {record.payload_hash}
              </p>
              <p>
                <span className="font-mono">fetched_at:</span> {record.fetched_at}
              </p>
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
