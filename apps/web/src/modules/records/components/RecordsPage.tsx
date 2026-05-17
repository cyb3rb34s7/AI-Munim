import { useState } from 'react';
import { motion } from 'framer-motion';

import { Loader } from '@/shared/components';
import { fadeUp } from '@/shared/utils/motion';

import { useRecord } from '../hooks/useRecord';
import { useRecords } from '../hooks/useRecords';
import { RecordsSourceFilter } from '../types/record.types';
import { RecordDrawer } from './RecordDrawer';
import { RecordsTable } from './RecordsTable';

const RECORDS_LIMIT = 200;

const FILTER_OPTIONS = [
  { value: RecordsSourceFilter.All, label: 'All' },
  { value: RecordsSourceFilter.Shopify, label: 'Shopify' },
  { value: RecordsSourceFilter.MetaAds, label: 'Meta Ads' },
  { value: RecordsSourceFilter.Shiprocket, label: 'Shiprocket' },
] as const;

export function RecordsPage() {
  const [filter, setFilter] = useState<RecordsSourceFilter>(RecordsSourceFilter.All);
  const { items, isLoading, error } = useRecords(filter);
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

      <div className="flex flex-wrap items-center gap-2">
        {FILTER_OPTIONS.map((option) => {
          const isActive = option.value === filter;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setFilter(option.value)}
              className={
                'inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors ' +
                (isActive
                  ? 'border-transparent bg-primary text-primary-fg shadow-sm'
                  : 'border-border bg-surface-elevated text-fg-muted hover:bg-surface-subtle')
              }
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {isLoading && <Loader label="Loading records…" />}
      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          <p className="font-medium">Could not load records</p>
          <p className="mt-1 font-mono text-xs">{error.message}</p>
        </div>
      )}
      {items && (
        <>
          <RecordsTable items={items} onRowClick={setSelectedId} />
          {items.length === RECORDS_LIMIT && (
            <p className="text-xs text-fg-subtle">
              Showing first {RECORDS_LIMIT} of your records — sync filtering coming soon.
            </p>
          )}
        </>
      )}

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
