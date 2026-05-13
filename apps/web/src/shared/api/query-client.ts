import { QueryClient } from '@tanstack/react-query';

import { ApiError, ContractMismatchError } from './errors';

/**
 * One shared TanStack Query client.
 *
 * - Contract mismatches never retry — the contract is broken, retrying will not
 *   fix it; the error must be surfaced.
 * - 4xx errors never retry — they are caller-fault, retrying will not help.
 * - Everything else retries twice with exponential backoff (TanStack default).
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (error instanceof ContractMismatchError) return false;
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});
