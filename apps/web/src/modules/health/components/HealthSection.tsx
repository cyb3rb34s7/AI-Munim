import { useHealth } from '../hooks/useHealth';
import { HealthCard } from './HealthCard';

/**
 * Connector component: invokes the data hook and passes results to the dumb
 * HealthCard. Only components in this role may call hooks per
 * docs/conventions.md §12.4.
 */
export function HealthSection() {
  const { health, traceId, isLoading, error } = useHealth();

  return (
    <HealthCard
      loading={isLoading}
      error={error}
      health={health}
      traceId={traceId}
    />
  );
}
