import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { Avatar, AvatarFallback, Button } from '@/shared/ui';
import type { ChatMessage } from '@/modules/chat/hooks/useChat';
import { fadeUp } from '@/shared/utils/motion';
import { MessageBubble } from './MessageBubble';

const SUGGESTIONS = [
  'How many orders are paid online?',
  'Compare my Meta ad spend to my Shopify revenue',
  'Which customer has the worst RTO history, and what are they pending?',
  'Which Meta campaign drives the most purchases?',
] as const;

const THINKING_PHASES = [
  'Looking up your data…',
  'Cross-referencing shipment history…',
  'Composing answer…',
] as const;

const PHASE_INTERVAL_MS = 1500;

interface Props {
  messages: ChatMessage[];
  isPending: boolean;
  onSuggest: (prompt: string) => void;
}

function TypingIndicator() {
  const [phaseIndex, setPhaseIndex] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setPhaseIndex((prev) => (prev + 1) % THINKING_PHASES.length);
    }, PHASE_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="flex items-start gap-3">
      <Avatar className="h-9 w-9 shrink-0">
        <AvatarFallback className="bg-accent text-accent-fg font-semibold">M</AvatarFallback>
      </Avatar>
      <div className="rounded-2xl rounded-tl-sm bg-surface-elevated border border-border px-4 py-3 inline-flex flex-col gap-2">
        <div className="inline-flex gap-1">
          <span className="h-2 w-2 rounded-full bg-fg-subtle animate-bounce [animation-delay:-0.3s]" />
          <span className="h-2 w-2 rounded-full bg-fg-subtle animate-bounce [animation-delay:-0.15s]" />
          <span className="h-2 w-2 rounded-full bg-fg-subtle animate-bounce" />
        </div>
        <AnimatePresence mode="wait">
          <motion.span
            key={phaseIndex}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            className="text-xs text-fg-muted"
          >
            {THINKING_PHASES[phaseIndex]}
          </motion.span>
        </AnimatePresence>
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
          Ask anything across Shopify, Meta Ads, and Shiprocket
        </h2>
        <p className="mt-1.5 text-sm text-fg-muted">
          Every numeric claim is grounded in a real row from one of your connectors. Hover any
          citation to see the source.
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

function PersistentSuggestions({ onSuggest }: { onSuggest: (prompt: string) => void }) {
  return (
    <div className="mt-4 flex flex-wrap gap-2">
      {SUGGESTIONS.map((s) => (
        <Button key={s} variant="secondary" size="sm" onClick={() => onSuggest(s)}>
          {s}
        </Button>
      ))}
    </div>
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
      <PersistentSuggestions onSuggest={onSuggest} />
      <div ref={endRef} />
    </div>
  );
}
