/**
 * Error codes returned by the backend in the error envelope.
 *
 * Mirrors apps/api/src/munim/shared/constants.py::ErrorCode. Per
 * docs/conventions.md §7 we never compare against the raw string at the call
 * site; we compare against this const. CI will eventually assert the two
 * mirrors match.
 */

export const ErrorCode = {
  SystemUnexpected: 'system.unexpected',
  SystemDatabaseUnavailable: 'system.database_unavailable',
  ValidationMissingField: 'validation.missing_field',
  ValidationBadFormat: 'validation.bad_format',
} as const;

export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];
