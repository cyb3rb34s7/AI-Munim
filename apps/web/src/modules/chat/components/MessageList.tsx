import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { Avatar, AvatarFallback, Button } from '@/shared/ui';
import type { ChatMessage } from '@/modules/chat/hooks/useChat';
import { fadeUp } from '@/shared/utils/motion';
import { MessageBubble } from './MessageBubble';

const SUGGESTIONS = [
  'How many orders are paid online?',
  'What is my average order value this week?',
  'Show me the highest-RTO-risk pincodes',
  'Which orders look like RTO risks?',
] as const;

interface Props {
  messages: ChatMessage[];
  isPending: boolean;
  onSuggest: (prompt: string) => void;
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <Avatar className="h-9 w-9 shrink-0">
        <AvatarFallback className="bg-accent text-accent-fg font-semibold">M</AvatarFallback>
      </Avatar>
      <div className="rounded-2xl rounded-tl-sm bg-surface-elevated border border-border px-4 py-3 inline-flex gap-1">
        <span className="h-2 w-2 rounded-full bg-fg-subtle animate-bounce [animation-delay:-0.3s]" />
        <span className="h-2 w-2 rounded-full bg-fg-subtle animate-bounce [animation-delay:-0.15s]" />
        <span className="h-2 w-2 rounded-full bg-fg-subtle animate-bounce" />
      </div>
    </div>
  );
}

function EmptyState({ onSuggest }: { onSuggest: (prompt: string) => void }) {
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="flex flex-col items-center justify-center text-center gap-6 py-12"
    >
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-accent text-accent-fg">
        <Sparkles className="h-6 w-6" />
      </div>
      <div className="max-w-md">
        <h2 className="text-xl font-semibold tracking-tight text-fg">
          Ask about your sales, orders, or RTO risk
        </h2>
        <p className="mt-1.5 text-sm text-fg-muted">
          Every numeric claim is grounded in a real row. Hover any citation badge to see the source.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center max-w-xl">
        {SUGGESTIONS.map((s) => (
          <Button key={s} variant="secondary" size="sm" onClick={() => onSuggest(s)}>
            {s}
          </Button>
        ))}
      </div>
    </motion.div>
  );
}

export function MessageList({ messages, isPending, onSuggest }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isPending]);

  if (messages.length === 0 && !isPending) {
    return <EmptyState onSuggest={onSuggest} />;
  }

  return (
    <div className="flex flex-col gap-4">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      {isPending && <TypingIndicator />}
      <div ref={endRef} />
    </div>
  );
}
