import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchCurrentUser,
  logout,
  onboard,
  startDemo,
  type StartDemoInput,
} from '../api/client';

export const AUTH_QUERY_KEY = ['auth', 'me'] as const;

export function useCurrentUser() {
  return useQuery({
    queryKey: AUTH_QUERY_KEY,
    queryFn: fetchCurrentUser,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useStartDemo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StartDemoInput) => startDemo(input),
    onSuccess: (user) => {
      queryClient.setQueryData(AUTH_QUERY_KEY, user);
    },
  });
}

export function useOnboard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: onboard,
    onSuccess: () => {
      // Records + connectors lists change after seed — invalidate them
      // so the user lands on /chat with fresh data, not a stale cache.
      queryClient.invalidateQueries({ queryKey: ['records'] });
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(AUTH_QUERY_KEY, null);
      queryClient.removeQueries();
    },
  });
}
