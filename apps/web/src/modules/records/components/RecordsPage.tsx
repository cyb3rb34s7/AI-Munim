import { useState } from 'react';
import { motion } from 'framer-motion';

import { Loader } from '@/shared/components';
import { fadeUp } from '@/shared/utils/motion';

import { useRecord } from '../hooks/useRecord';
import { useRecords } from '../hooks/useRecords';
import { RecordDrawer } from './RecordDrawer';
import { RecordsTable } from './RecordsTable';

export function RecordsPage() {
  const { items, isLoading, error } = useRecords();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { record, isLoading: detailLoading, error: detailError } = useRecord(selectedId);

  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="mx-auto max-w-5xl space-y-6 p-8"
    >
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-fg">Records</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Universal storage. Every row carries its source, the original raw payload, and our
          normalized projection. Click a row to see both side by side.
        </p>
      </section>

      {isLoading && <Loader label="Loading records…" />}
      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
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
    </motion.div>
  );
}
