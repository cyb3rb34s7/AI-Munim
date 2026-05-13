import { useMutation, useQueryClient } from '@tanstack/react-query';

import { CONNECTORS_QUERY_KEY, postConnect } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

export function useConnectMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: ConnectorName) => postConnect(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONNECTORS_QUERY_KEY });
    },
  });
}
