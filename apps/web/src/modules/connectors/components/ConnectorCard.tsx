import { Button, Card, StatusBadge } from '@/shared/components';

import { EnableDemoButton } from './EnableDemoButton';
import type { ConnectorView, ConnectorName, CredentialStatus } from '../types/connector.types';

interface ConnectorCardProps {
  view: ConnectorView;
  syncing: boolean;
  startingOAuth: boolean;
  onConnectReal: (name: ConnectorName) => void;
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
  syncing,
  startingOAuth,
  onConnectReal,
  onSync,
}: ConnectorCardProps) {
  const isConnected = view.status !== null;
  const orderCount = view.record_counts.find((c) => c.entity_type === 'order')?.count ?? 0;
  const shipmentCount = view.record_counts.find((c) => c.entity_type === 'shipment')?.count ?? 0;
  const adSpendCount = view.record_counts.find((c) => c.entity_type === 'ad_spend')?.count ?? 0;
  const primaryCount = view.is_demo
    ? view.name === 'shiprocket'
      ? shipmentCount
      : adSpendCount
    : orderCount;
  const primaryLabel = view.is_demo
    ? view.name === 'shiprocket'
      ? 'Shipments synced'
      : 'Ad-spend rows synced'
    : 'Orders synced';

  return (
    <Card
      title={LABELS[view.name as ConnectorName] ?? view.name}
      trailing={
        <div className="flex items-center gap-2">
          {view.is_demo && <StatusBadge tone="muted">demo</StatusBadge>}
          {view.status ? (
            <StatusBadge tone={STATUS_TONE[view.status]}>{view.status}</StatusBadge>
          ) : (
            <StatusBadge tone="muted">not connected</StatusBadge>
          )}
        </div>
      }
    >
      <div className="space-y-4 text-sm">
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1">
          <dt className="text-fg-muted">{primaryLabel}</dt>
          <dd className="font-mono">{primaryCount}</dd>
          <dt className="text-fg-muted">Last sync</dt>
          <dd className="font-mono">{view.last_sync_at ?? '—'}</dd>
        </dl>
        <div className="flex flex-wrap gap-2">
          {!isConnected && view.is_demo && <EnableDemoButton connectorName={view.name} />}
          {!isConnected && !view.is_demo && (
            <Button
              variant="primary"
              onClick={() => onConnectReal(view.name as ConnectorName)}
              loading={startingOAuth}
            >
              Connect to your store
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
