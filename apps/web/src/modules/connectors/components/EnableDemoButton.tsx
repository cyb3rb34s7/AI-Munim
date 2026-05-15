import { Button } from '@/shared/components';
import { useConnectDemoMutation } from '../hooks/useConnectDemoMutation';
import type { ConnectorName } from '../types/connector.types';

interface EnableDemoButtonProps {
  connectorName: ConnectorName;
}

export function EnableDemoButton({ connectorName }: EnableDemoButtonProps) {
  const mutation = useConnectDemoMutation();
  return (
    <Button
      variant="secondary"
      onClick={() => mutation.mutate(connectorName)}
      loading={mutation.isPending}
    >
      {mutation.isPending ? 'Enabling…' : 'Enable demo data'}
    </Button>
  );
}
