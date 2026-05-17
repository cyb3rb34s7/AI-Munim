import { motion } from 'framer-motion';
import { Avatar, AvatarFallback } from '@/shared/ui';
import { CitedText } from './CitedText';
import { fadeUp } from '@/shared/utils/motion';
import type { ChatMessage } from '@/modules/chat/hooks/useChat';

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
        <Avatar className="h-9 w-9 shrink-0">
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
        {isUser ? (
          message.text
        ) : (
          <CitedText text={message.text} citations={message.citations} />
        )}
      </div>
    </motion.div>
  );
}
