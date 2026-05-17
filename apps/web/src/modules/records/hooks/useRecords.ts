import { useQuery } from '@tanstack/react-query';

import { RECORDS_LIST_QUERY_KEY, fetchRecords } from '../api/records.api';
import type { RecordsSourceFilter } from '../types/record.types';

export function useRecords(filter: RecordsSourceFilter) {
  const query = useQuery({
    queryKey: RECORDS_LIST_QUERY_KEY(filter),
    queryFn: () => fetchRecords(filter),
  });
  return {
    items: query.data?.data.items,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
