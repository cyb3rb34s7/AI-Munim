import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { CONNECTORS_QUERY_KEY, postConnectDemo } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

export function useConnectDemoMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: ConnectorName) => postConnectDemo(name),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: CONNECTORS_QUERY_KEY });
      toast.success(`Demo data enabled for ${response.data.connector.name} — click Sync to load.`);
    },
  });
}
