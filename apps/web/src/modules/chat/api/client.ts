import { z } from 'zod';
import { apiPost } from '@/shared/api';

const rowCitationSchema = z.object({
  record_id: z.number(),
  entity_type: z.string(),
  source_system: z.string(),
  source_id: z.string(),
  excerpt: z.record(z.string(), z.unknown()),
});

const chatResponseSchema = z.object({
  text: z.string(),
  citations: z.array(rowCitationSchema),
});

export type RowCitation = z.infer<typeof rowCitationSchema>;
export type ChatResponse = z.infer<typeof chatResponseSchema>;

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const { data } = await apiPost('chat/messages', chatResponseSchema, { json: { message } });
  return data;
}
