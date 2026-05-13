import { useQuery } from '@tanstack/react-query';

import { fetchHealth, HEALTH_QUERY_KEY } from '../api/health.api';

export function useHealth() {
  const query = useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  return {
    health: query.data?.data,
    traceId: query.data?.traceId,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  };
}
