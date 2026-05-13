import { useQuery } from '@tanstack/react-query';

import { RECORDS_LIST_QUERY_KEY, fetchRecords } from '../api/records.api';

export function useRecords() {
  const query = useQuery({
    queryKey: RECORDS_LIST_QUERY_KEY,
    queryFn: fetchRecords,
  });
  return {
    items: query.data?.data.items,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
