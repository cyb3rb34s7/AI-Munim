import { useQuery } from '@tanstack/react-query';

import { CONNECTORS_QUERY_KEY, fetchConnectors } from '../api/connectors.api';

export function useConnectors() {
  const query = useQuery({
    queryKey: CONNECTORS_QUERY_KEY,
    queryFn: fetchConnectors,
  });
  return {
    connectors: query.data?.data.connectors,
    traceId: query.data?.traceId,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
