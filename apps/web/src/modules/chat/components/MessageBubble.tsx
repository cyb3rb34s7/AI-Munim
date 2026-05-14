import { motion } from 'framer-motion';
import { Avatar, AvatarFallback } from '@/shared/ui';
import { CitationBadge } from './CitationBadge';
import { fadeUp } from '@/shared/utils/motion';
import type { ChatMessage } from '@/modules/chat/hooks/useChat';
import type { RowCitation } from '@/modules/chat/api/client';

const CITE_RE = /\[cite:([\d,\s]+)\]/g;

type Part = { kind: 'text'; value: string } | { kind: 'cite'; ids: number[] };

function parseText(text: string): Part[] {
  const parts: Part[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  CITE_RE.lastIndex = 0;
  while ((match = CITE_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ kind: 'text', value: text.slice(lastIndex, match.index) });
    }
    const ids = match[1]
      .split(',')
      .map((s) => Number.parseInt(s.trim(), 10))
      .filter((n) => Number.isFinite(n));
    parts.push({ kind: 'cite', ids });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push({ kind: 'text', value: text.slice(lastIndex) });
  }
  return parts;
}

function renderAssistantText(text: string, citations: RowCitation[] | undefined) {
  const parts = parseText(text);
  return parts.map((part, i) => {
    if (part.kind === 'text') {
      return <span key={i}>{part.value}</span>;
    }
    return (
      <span key={i} className="inline-flex items-baseline">
        {part.ids.map((id) => {
          const citation = citations?.find((c) => c.id === id);
          return citation ? <CitationBadge key={id} citation={citation} /> : null;
        })}
      </span>
    );
  });
}

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className={isUser ? 'flex justify-end' : 'flex items-start gap-3'}
    >
      {!isUser && (
        <Avatar className="h-9 w-9 shrink-0 bg-accent text-accent-fg">
          <AvatarFallback className="bg-accent text-accent-fg font-semibold">M</AvatarFallback>
        </Avatar>
      )}
      <div
        className={
          isUser
            ? 'max-w-[75%] rounded-2xl rounded-br-sm bg-primary text-primary-fg px-4 py-2.5 text-sm whitespace-pre-wrap'
            : 'max-w-[75%] rounded-2xl rounded-tl-sm bg-surface-elevated border border-border px-4 py-2.5 text-sm leading-relaxed text-fg whitespace-pre-wrap'
        }
      >
        {isUser ? message.text : renderAssistantText(message.text, message.citations)}
      </div>
    </motion.div>
  );
}
