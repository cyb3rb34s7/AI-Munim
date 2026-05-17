/**
 * The single API client. ky calls + envelope unwrap + Zod validation at the
 * boundary, per docs/conventions.md §12.3.
 *
 * Components and hooks NEVER see the envelope. They get `{ data, traceId }` on
 * success, or one of two typed exceptions on failure:
 *   - `ApiError` for a well-formed error envelope from the backend.
 *   - `ContractMismatchError` for a response that did not match the expected
 *     shape (always a real bug).
 */

import ky, { HTTPError, type KyInstance, type Options } from 'ky';
import { z } from 'zod';

import { ApiError, ContractMismatchError, type ApiErrorInfo } from './errors';
import { errorEnvelopeSchema } from '../types/api';

const TRACE_ID_HEADER = 'X-Trace-Id';
const API_PREFIX = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

// Envelope shell we always expect on a 2xx response. The `data` field is
// validated separately with the caller-provided schema.
const successShellSchema = z.object({
  success: z.literal(true),
  data: z.unknown(),
  trace_id: z.string(),
});

const base: KyInstance = ky.create({
  prefixUrl: API_PREFIX,
  timeout: 90_000,
  retry: { limit: 1, methods: ['get'] },
  credentials: 'include',
});

export interface ApiResponse<T> {
  data: T;
  traceId: string;
}

export function apiGet<T>(
  path: string,
  dataSchema: z.ZodType<T>,
  options?: Options,
): Promise<ApiResponse<T>> {
  return execute(() => base.get(stripLeadingSlash(path), options), dataSchema);
}

export function apiPost<T>(
  path: string,
  dataSchema: z.ZodType<T>,
  options?: Options,
): Promise<ApiResponse<T>> {
  return execute(() => base.post(stripLeadingSlash(path), options), dataSchema);
}

async function execute<T>(
  exec: () => Promise<Response>,
  dataSchema: z.ZodType<T>,
): Promise<ApiResponse<T>> {
  let response: Response;
  try {
    response = await exec();
  } catch (error) {
    if (error instanceof HTTPError) {
      throw new ApiError(await readErrorEnvelope(error.response));
    }
    throw error;
  }

  const body: unknown = await response.json();
  const shellResult = successShellSchema.safeParse(body);
  if (!shellResult.success) {
    throw new ContractMismatchError(
      'Backend success response did not match the envelope shell.',
      shellResult.error,
      body,
    );
  }

  const dataResult = dataSchema.safeParse(shellResult.data.data);
  if (!dataResult.success) {
    throw new ContractMismatchError(
      'Backend success response had the envelope shell but `data` did not match the expected schema.',
      dataResult.error,
      body,
    );
  }

  return { data: dataResult.data, traceId: shellResult.data.trace_id };
}

async function readErrorEnvelope(response: Response): Promise<ApiErrorInfo> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const parsed = errorEnvelopeSchema.safeParse(body);
  if (!parsed.success) {
    throw new ContractMismatchError(
      `Backend returned ${response.status} but the body did not match the error envelope.`,
      parsed.error,
      body,
    );
  }
  return {
    code: parsed.data.error.code,
    message: parsed.data.error.message,
    details: parsed.data.error.details ?? null,
    traceId: parsed.data.trace_id,
    status: response.status,
  };
}

function stripLeadingSlash(path: string): string {
  return path.startsWith('/') ? path.slice(1) : path;
}

export { TRACE_ID_HEADER };
