/**
 * Typed errors thrown by the API client.
 *
 * `ApiError` represents a well-formed backend error envelope. Components and
 * hooks should branch on `error.code` (a typed `ErrorCode`), never on
 * `error.message`.
 *
 * `ContractMismatchError` represents a response that did not match the expected
 * shape (Zod parse failure on the envelope or on the data). This is always a
 * real bug, not a user-visible condition - surface it loudly during development
 * and report it to observability in production.
 */

export interface ApiErrorInfo {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  traceId: string;
  status: number;
}

export class ApiError extends Error {
  readonly code: string;
  readonly traceId: string;
  readonly status: number;
  readonly details: Record<string, unknown> | null;

  constructor(info: ApiErrorInfo) {
    super(info.message);
    this.name = 'ApiError';
    this.code = info.code;
    this.traceId = info.traceId;
    this.status = info.status;
    this.details = info.details;
  }
}

export class ContractMismatchError extends Error {
  readonly zodError: unknown;
  readonly responseBody: unknown;

  constructor(message: string, zodError: unknown, responseBody: unknown) {
    super(message);
    this.name = 'ContractMismatchError';
    this.zodError = zodError;
    this.responseBody = responseBody;
  }
}
