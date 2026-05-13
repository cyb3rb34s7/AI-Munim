import { z } from 'zod';

export const recordSummarySchema = z.object({
  id: z.number().int(),
  source_system: z.string(),
  source_id: z.string(),
  entity_type: z.string(),
  fetched_at: z.string(),
});

export const recordDetailSchema = z.object({
  id: z.number().int(),
  source_system: z.string(),
  source_id: z.string(),
  entity_type: z.string(),
  fetched_at: z.string(),
  payload_hash: z.string(),
  raw: z.record(z.unknown()),
  normalized: z.record(z.unknown()),
});

export const recordsListResponseSchema = z.object({
  items: z.array(recordSummarySchema),
  limit: z.number().int(),
});

export type RecordSummary = z.infer<typeof recordSummarySchema>;
export type RecordDetail = z.infer<typeof recordDetailSchema>;
export type RecordsListResponse = z.infer<typeof recordsListResponseSchema>;
