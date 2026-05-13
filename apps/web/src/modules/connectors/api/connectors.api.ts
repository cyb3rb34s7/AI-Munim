import { apiGet, apiPost, type ApiResponse } from '@/shared/api';

import {
  connectorListResponseSchema,
  connectResponseSchema,
  syncResponseSchema,
  type ConnectorListResponse,
  type ConnectorName,
  type ConnectResponse,
  type SyncResponse,
} from '../types/connector.types';

export const CONNECTORS_QUERY_KEY = ['connectors'] as const;

export function fetchConnectors(): Promise<ApiResponse<ConnectorListResponse>> {
  return apiGet('/connectors', connectorListResponseSchema);
}

export function postConnect(name: ConnectorName): Promise<ApiResponse<ConnectResponse>> {
  return apiPost(`/connectors/${name}/connect`, connectResponseSchema);
}

export function postSync(name: ConnectorName): Promise<ApiResponse<SyncResponse>> {
  return apiPost(`/connectors/${name}/sync`, syncResponseSchema);
}
