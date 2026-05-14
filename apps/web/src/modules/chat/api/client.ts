import { z } from 'zod';
import { apiPost } from '@/shared/api';

const rowCitationSchema = z.object({
  id: z.number(),
  source_id: z.string(),
  source_system: z.string(),
  entity_type: z.string(),
});

const chatResponseSchema = z.object({
  text: z.string(),
  used_citations: z.array(z.number()),
  available_citations: z.array(rowCitationSchema),
});

export type RowCitation = z.infer<typeof rowCitationSchema>;
export type ChatResponse = z.infer<typeof chatResponseSchema>;

export async function sendChatMessage(prompt: string): Promise<ChatResponse> {
  const { data } = await apiPost('chat/messages', chatResponseSchema, { json: { prompt } });
  return data;
}
