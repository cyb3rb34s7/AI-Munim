import { Loader } from '@/shared/components';

import { ConnectorCard } from './ConnectorCard';
import type { ConnectorName, ConnectorView } from '../types/connector.types';

interface ConnectorsGridProps {
  connectors: ConnectorView[] | undefined;
  isLoading: boolean;
  error: Error | null;
  connectingName: ConnectorName | null;
  syncingName: ConnectorName | null;
  onConnect: (name: ConnectorName) => void;
  onSync: (name: ConnectorName) => void;
}

export function ConnectorsGrid({
  connectors,
  isLoading,
  error,
  connectingName,
  syncingName,
  onConnect,
  onSync,
}: ConnectorsGridProps) {
  if (isLoading) return <Loader label="Loading connectors…" />;
  if (error) {
    return (
      <div className="rounded-md border border-error/30 bg-error/10 p-4 text-sm text-error">
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
          connecting={connectingName === view.name}
          syncing={syncingName === view.name}
          onConnect={onConnect}
          onSync={onSync}
        />
      ))}
    </div>
  );
}
