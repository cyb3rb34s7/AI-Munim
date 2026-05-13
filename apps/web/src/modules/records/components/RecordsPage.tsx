import { useState } from 'react';

import { Loader } from '@/shared/components';

import { useRecord } from '../hooks/useRecord';
import { useRecords } from '../hooks/useRecords';
import { RecordDrawer } from './RecordDrawer';
import { RecordsTable } from './RecordsTable';

export function RecordsPage() {
  const { items, isLoading, error } = useRecords();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { record, isLoading: detailLoading, error: detailError } = useRecord(selectedId);

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold">Records</h2>
        <p className="mt-1 text-sm text-muted">
          Universal storage. Every row carries its source, the original raw payload, and our
          normalized projection. Click a row to see both side by side.
        </p>
      </section>

      {isLoading && <Loader label="Loading records…" />}
      {error && (
        <div className="rounded-md border border-error/30 bg-error/10 p-4 text-sm text-error">
          <p className="font-medium">Could not load records</p>
          <p className="mt-1 font-mono text-xs">{error.message}</p>
        </div>
      )}
      {items && <RecordsTable items={items} onRowClick={setSelectedId} />}

      {selectedId !== null && (
        <RecordDrawer
          record={record}
          isLoading={detailLoading}
          error={detailError}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
