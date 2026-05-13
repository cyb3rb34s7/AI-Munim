import { apiGet, type ApiResponse } from '@/shared/api';

import {
  recordDetailSchema,
  recordsListResponseSchema,
  type RecordDetail,
  type RecordsListResponse,
} from '../types/record.types';

export const RECORDS_LIST_QUERY_KEY = ['records'] as const;
export const RECORD_DETAIL_QUERY_KEY = (id: number) => ['records', id] as const;

export function fetchRecords(): Promise<ApiResponse<RecordsListResponse>> {
  return apiGet('/records', recordsListResponseSchema);
}

export function fetchRecord(id: number): Promise<ApiResponse<RecordDetail>> {
  return apiGet(`/records/${id}`, recordDetailSchema);
}
