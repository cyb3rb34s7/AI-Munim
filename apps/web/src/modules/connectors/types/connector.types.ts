import { z } from 'zod';

export const ConnectorName = {
  Shopify: 'shopify',
  MetaAds: 'meta_ads',
  Shiprocket: 'shiprocket',
} as const;
export type ConnectorName = (typeof ConnectorName)[keyof typeof ConnectorName];

export const CredentialStatus = {
  Connected: 'connected',
  Demo: 'demo',
  Error: 'error',
} as const;
export type CredentialStatus = (typeof CredentialStatus)[keyof typeof CredentialStatus];

export const entityCountSchema = z.object({
  entity_type: z.string(),
  count: z.number().int().nonnegative(),
});

export const connectorViewSchema = z.object({
  name: z.enum(['shopify', 'meta_ads', 'shiprocket']),
  status: z.enum(['connected', 'demo', 'error']).nullable(),
  last_sync_at: z.string().nullable(),
  record_counts: z.array(entityCountSchema),
});

export const connectorListResponseSchema = z.object({
  connectors: z.array(connectorViewSchema),
});

export const connectResponseSchema = z.object({
  connector: connectorViewSchema,
});

export const syncResponseSchema = z.object({
  rows_upserted: z.number().int().nonnegative(),
  rows_skipped: z.number().int().nonnegative(),
  started_at: z.string(),
  finished_at: z.string(),
  connector: connectorViewSchema,
});

export type EntityCount = z.infer<typeof entityCountSchema>;
export type ConnectorView = z.infer<typeof connectorViewSchema>;
export type ConnectorListResponse = z.infer<typeof connectorListResponseSchema>;
export type ConnectResponse = z.infer<typeof connectResponseSchema>;
export type SyncResponse = z.infer<typeof syncResponseSchema>;

export const startOAuthResponseSchema = z.object({
  authorize_url: z.string().url(),
});

export type StartOAuthResponse = z.infer<typeof startOAuthResponseSchema>;
