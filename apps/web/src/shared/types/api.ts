/**
 * Zod schemas for the API response envelopes.
 *
 * The frontend parses every backend response through these schemas at the API
 * client boundary (see ../api/client.ts). If the contract drifts we throw a
 * `ContractMismatchError` at the call site, not deep in a component.
 *
 * Mirrors apps/api/src/munim/shared/responses.py.
 */

import { z } from 'zod';

export const errorPayloadSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.record(z.unknown()).nullable().optional(),
});

export const errorEnvelopeSchema = z.object({
  success: z.literal(false),
  error: errorPayloadSchema,
  trace_id: z.string(),
});

export const successEnvelopeSchema = <T extends z.ZodTypeAny>(dataSchema: T) =>
  z.object({
    success: z.literal(true),
    data: dataSchema,
    trace_id: z.string(),
  });

export type ErrorPayload = z.infer<typeof errorPayloadSchema>;
export type ErrorEnvelope = z.infer<typeof errorEnvelopeSchema>;
