import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useConnectMutation } from '../hooks/useConnectMutation';
import { useConnectors } from '../hooks/useConnectors';
import { useStartOAuthMutation } from '../hooks/useStartOAuthMutation';
import { useSyncMutation } from '../hooks/useSyncMutation';
import type { ConnectorName, SyncResponse } from '../types/connector.types';
import { ConnectorsGrid } from './ConnectorsGrid';
import { ShopOAuthModal } from './ShopOAuthModal';

const DEFAULT_SHOP = 'munim-dev';

export function ConnectorsPage() {
  const { connectors, isLoading, error } = useConnectors();
  const connect = useConnectMutation();
  const sync = useSyncMutation();
  const startOAuth = useStartOAuthMutation();

  const [lastSync, setLastSync] = useState<SyncResponse | null>(null);
  const [modalForName, setModalForName] = useState<ConnectorName | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  // Show a success banner after OAuth round-trip lands us at /connectors?connected=shopify.
  const [connectedNotice, setConnectedNotice] = useState<string | null>(null);
  useEffect(() => {
    const connected = searchParams.get('connected');
    if (connected) {
      setConnectedNotice(connected);
      // Clean the URL so a refresh doesn't show the banner forever.
      const next = new URLSearchParams(searchParams);
      next.delete('connected');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const handleConnect = (name: ConnectorName) => {
    connect.mutate(name);
  };
  const handleConnectReal = (name: ConnectorName) => {
    setModalForName(name);
  };
  const handleOAuthSubmit = (shop: string) => {
    if (!modalForName) return;
    startOAuth.mutate(
      { name: modalForName, shop },
      {
        onSuccess: (resp) => {
          window.location.href = resp.data.authorize_url;
        },
      },
    );
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
          Three connectors behind one abstraction. Use <em>Connect (demo)</em> to load a frozen
          fixture, or <em>Connect to your store</em> to authenticate against your real Shopify shop.
        </p>
      </section>

      {connectedNotice && (
        <div className="rounded-md border border-success/30 bg-success/10 p-4 text-sm">
          <p className="font-medium text-success">
            {connectedNotice} connected. Click <em>Sync now</em> on the card to pull your orders.
          </p>
        </div>
      )}

      <ConnectorsGrid
        connectors={connectors}
        isLoading={isLoading}
        error={error}
        connectingName={connect.isPending ? (connect.variables ?? null) : null}
        syncingName={sync.isPending ? (sync.variables ?? null) : null}
        startingOAuthName={startOAuth.isPending ? modalForName : null}
        onConnect={handleConnect}
        onConnectReal={handleConnectReal}
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

      <ShopOAuthModal
        open={modalForName !== null}
        defaultShop={DEFAULT_SHOP}
        submitting={startOAuth.isPending}
        error={startOAuth.error}
        onSubmit={handleOAuthSubmit}
        onClose={() => setModalForName(null)}
      />
    </div>
  );
}
