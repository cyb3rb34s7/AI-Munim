import { apiGet, type ApiResponse } from '@/shared/api';

import { healthDataSchema, type HealthData } from '../types/health.types';

export const HEALTH_QUERY_KEY = ['health'] as const;

export function fetchHealth(): Promise<ApiResponse<HealthData>> {
  return apiGet('/health', healthDataSchema);
}
