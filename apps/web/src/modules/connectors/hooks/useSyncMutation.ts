import { useMutation, useQueryClient } from '@tanstack/react-query';

import { CONNECTORS_QUERY_KEY, postSync } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

const RECORDS_QUERY_KEY = ['records'];

export function useSyncMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: ConnectorName) => postSync(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONNECTORS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: RECORDS_QUERY_KEY });
    },
  });
}
