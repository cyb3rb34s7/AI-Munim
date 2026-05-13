import { useMutation, useQueryClient } from '@tanstack/react-query';

import { RECORDS_LIST_QUERY_KEY } from '@/modules/records';

import { CONNECTORS_QUERY_KEY, postSync } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

export function useSyncMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: ConnectorName) => postSync(name),
    onSuccess: () => {
      // A sync writes new record rows; invalidate both caches so the
      // Connectors page row counts and the Records page table both refetch.
      // Import the records key from the records module's public surface so a
      // future namespacing change there propagates here automatically.
      queryClient.invalidateQueries({ queryKey: CONNECTORS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: RECORDS_LIST_QUERY_KEY });
    },
  });
}
