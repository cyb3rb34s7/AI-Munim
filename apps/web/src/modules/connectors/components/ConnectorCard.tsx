import { Button, Card, StatusBadge } from '@/shared/components';

import type { ConnectorView, ConnectorName, CredentialStatus } from '../types/connector.types';

interface ConnectorCardProps {
  view: ConnectorView;
  connecting: boolean;
  syncing: boolean;
  onConnect: (name: ConnectorName) => void;
  onSync: (name: ConnectorName) => void;
}

const STATUS_TONE: Record<CredentialStatus, 'success' | 'accent' | 'error'> = {
  connected: 'success',
  demo: 'accent',
  error: 'error',
};

const LABELS: Record<ConnectorName, string> = {
  shopify: 'Shopify',
  meta_ads: 'Meta Ads',
  shiprocket: 'Shiprocket',
};

export function ConnectorCard({
  view,
  connecting,
  syncing,
  onConnect,
  onSync,
}: ConnectorCardProps) {
  const isConnected = view.status !== null;
  const orderCount = view.record_counts.find((c) => c.entity_type === 'order')?.count ?? 0;

  return (
    <Card
      title={LABELS[view.name as ConnectorName] ?? view.name}
      trailing={
        view.status ? (
          <StatusBadge tone={STATUS_TONE[view.status]}>{view.status}</StatusBadge>
        ) : (
          <StatusBadge tone="muted">not connected</StatusBadge>
        )
      }
    >
      <div className="space-y-4 text-sm">
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1">
          <dt className="text-muted">Orders synced</dt>
          <dd className="font-mono">{orderCount}</dd>
          <dt className="text-muted">Last sync</dt>
          <dd className="font-mono">{view.last_sync_at ?? '—'}</dd>
        </dl>
        <div className="flex gap-2">
          {!isConnected && (
            <Button onClick={() => onConnect(view.name as ConnectorName)} loading={connecting}>
              Connect (demo)
            </Button>
          )}
          {isConnected && (
            <Button
              variant="secondary"
              onClick={() => onSync(view.name as ConnectorName)}
              loading={syncing}
            >
              Sync now
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
