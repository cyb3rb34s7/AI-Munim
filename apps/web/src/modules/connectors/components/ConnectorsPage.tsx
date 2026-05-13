import { useState } from 'react';

import { useConnectMutation } from '../hooks/useConnectMutation';
import { useConnectors } from '../hooks/useConnectors';
import { useSyncMutation } from '../hooks/useSyncMutation';
import type { ConnectorName, SyncResponse } from '../types/connector.types';
import { ConnectorsGrid } from './ConnectorsGrid';

export function ConnectorsPage() {
  const { connectors, isLoading, error } = useConnectors();
  const connect = useConnectMutation();
  const sync = useSyncMutation();
  const [lastSync, setLastSync] = useState<SyncResponse | null>(null);

  const handleConnect = (name: ConnectorName) => {
    connect.mutate(name);
  };
  const handleSync = (name: ConnectorName) => {
    sync.mutate(name, {
      onSuccess: (resp) => setLastSync(resp.data),
    });
  };

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold">Connectors</h2>
        <p className="mt-1 text-sm text-muted">
          Three connectors behind one abstraction. Click <em>Connect (demo)</em> to load a frozen
          fixture, then <em>Sync now</em> to upsert into the universal <code>record</code> table.
        </p>
      </section>

      <ConnectorsGrid
        connectors={connectors}
        isLoading={isLoading}
        error={error}
        connectingName={connect.isPending ? (connect.variables ?? null) : null}
        syncingName={sync.isPending ? (sync.variables ?? null) : null}
        onConnect={handleConnect}
        onSync={handleSync}
      />

      {lastSync && (
        <div className="rounded-md border border-success/30 bg-success/10 p-4 text-sm">
          <p className="font-medium text-success">
            Sync complete: {lastSync.rows_upserted} upserted, {lastSync.rows_skipped} unchanged.
          </p>
          <p className="mt-1 text-xs text-muted">
            Open the Records tab to inspect the rows + their original Shopify payloads.
          </p>
        </div>
      )}
    </div>
  );
}
