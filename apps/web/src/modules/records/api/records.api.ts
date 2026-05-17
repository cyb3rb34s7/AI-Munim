import { apiGet, type ApiResponse } from '@/shared/api';

import {
  recordDetailSchema,
  recordsListResponseSchema,
  type RecordDetail,
  type RecordsListResponse,
  type RecordsSourceFilter,
} from '../types/record.types';

export const RECORDS_LIST_QUERY_KEY = (filter: RecordsSourceFilter) =>
  ['records', { source: filter }] as const;
export const RECORD_DETAIL_QUERY_KEY = (id: number) => ['records', id] as const;

export function fetchRecords(
  filter: RecordsSourceFilter,
): Promise<ApiResponse<RecordsListResponse>> {
  const query = filter === 'all' ? '' : `?source_system=${filter}`;
  return apiGet(`/records${query}`, recordsListResponseSchema);
}

export function fetchRecord(id: number): Promise<ApiResponse<RecordDetail>> {
  return apiGet(`/records/${id}`, recordDetailSchema);
}
