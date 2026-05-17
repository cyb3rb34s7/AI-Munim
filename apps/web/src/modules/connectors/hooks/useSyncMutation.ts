import { useMutation, useQueryClient } from '@tanstack/react-query';

import { CONNECTORS_QUERY_KEY, postSync } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

export function useSyncMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: ConnectorName) => postSync(name),
    onSuccess: () => {
      // A sync writes new record rows; invalidate both caches so the
      // Connectors page row counts and the Records page table both refetch.
      // Records keys are namespaced as ['records', { source: ... }]; the
      // bare ['records'] prefix invalidates every variant.
      queryClient.invalidateQueries({ queryKey: CONNECTORS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ['records'] });
    },
  });
}
