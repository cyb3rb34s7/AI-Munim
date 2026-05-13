import { useQuery } from '@tanstack/react-query';

import { RECORD_DETAIL_QUERY_KEY, fetchRecord } from '../api/records.api';

export function useRecord(id: number | null) {
  const query = useQuery({
    queryKey: RECORD_DETAIL_QUERY_KEY(id ?? -1),
    queryFn: () => {
      if (id === null) {
        throw new Error('useRecord called with null id — guard with `enabled` instead.');
      }
      return fetchRecord(id);
    },
    enabled: id !== null,
  });
  return {
    record: query.data?.data,
    isLoading: query.isLoading,
    error: query.error,
  };
}
