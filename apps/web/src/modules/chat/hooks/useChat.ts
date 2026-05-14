import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { sendChatMessage, type RowCitation } from '@/modules/chat/api/client';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  citations?: RowCitation[];
  timestamp: number;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const mutation = useMutation({
    mutationFn: sendChatMessage,
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: data.text,
          citations: data.available_citations,
          timestamp: Date.now(),
        },
      ]);
    },
  });

  function send(prompt: string) {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', text: trimmed, timestamp: Date.now() },
    ]);
    mutation.mutate(trimmed);
  }

  return { messages, send, isPending: mutation.isPending, error: mutation.error };
}
