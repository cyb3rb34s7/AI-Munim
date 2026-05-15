import { Loader } from '@/shared/components';

import { ConnectorCard } from './ConnectorCard';
import type { ConnectorName, ConnectorView } from '../types/connector.types';

interface ConnectorsGridProps {
  connectors: ConnectorView[] | undefined;
  isLoading: boolean;
  error: Error | null;
  syncingName: ConnectorName | null;
  startingOAuthName: ConnectorName | null;
  onConnectReal: (name: ConnectorName) => void;
  onSync: (name: ConnectorName) => void;
}

export function ConnectorsGrid({
  connectors,
  isLoading,
  error,
  syncingName,
  startingOAuthName,
  onConnectReal,
  onSync,
}: ConnectorsGridProps) {
  if (isLoading) return <Loader label="Loading connectors…" />;
  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        <p className="font-medium">Could not load connectors</p>
        <p className="mt-1 font-mono text-xs">{error.message}</p>
      </div>
    );
  }
  if (!connectors || connectors.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {connectors.map((view) => (
        <ConnectorCard
          key={view.name}
          view={view}
          syncing={syncingName === view.name}
          startingOAuth={startingOAuthName === view.name}
          onConnectReal={onConnectReal}
          onSync={onSync}
        />
      ))}
    </div>
  );
}
