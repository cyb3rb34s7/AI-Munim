import { z } from 'zod';

import { apiGet, apiPost, ApiError } from '@/shared/api';

export const currentUserSchema = z.object({
  merchant_id: z.string(),
  user_id: z.string(),
  display_name: z.string(),
  created_at: z.string(),
});

export type CurrentUser = z.infer<typeof currentUserSchema>;

export interface StartDemoInput {
  display_name?: string;
}

export async function startDemo(input: StartDemoInput): Promise<CurrentUser> {
  const response = await apiPost('/auth/start', currentUserSchema, {
    json: input,
  });
  return response.data;
}

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  try {
    const response = await apiGet('/auth/me', currentUserSchema);
    return response.data;
  } catch (error) {
    if (error instanceof ApiError && error.code === 'auth.unauthenticated') {
      return null;
    }
    throw error;
  }
}

const logoutResponseSchema = z.object({ logged_out: z.boolean() });

export async function logout(): Promise<void> {
  await apiPost('/auth/logout', logoutResponseSchema);
}
