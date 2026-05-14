import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/shared/ui';
import { cn } from '@/shared/utils/cn';

interface Props {
  onSend: (prompt: string) => void;
  isPending: boolean;
}

const MAX_HEIGHT_PX = 160;

export function ChatInput({ onSend, isPending }: Props) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || isPending) return;
    onSend(trimmed);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    const t = e.target;
    t.style.height = 'auto';
    t.style.height = `${Math.min(t.scrollHeight, MAX_HEIGHT_PX)}px`;
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div
        className={cn(
          'flex items-end gap-2 rounded-2xl border border-border bg-surface px-3 py-2.5 shadow-sm',
          'focus-within:border-primary/40 transition-colors',
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your sales, orders, or RTO risk…"
          rows={1}
          disabled={isPending}
          className="flex-1 resize-none bg-transparent text-sm text-fg placeholder:text-fg-subtle outline-none leading-relaxed py-1.5 max-h-40"
        />
        <Button
          type="submit"
          size="icon"
          disabled={isPending || value.trim().length === 0}
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <div className="mt-1.5 text-[11px] text-fg-subtle text-right">Enter to send · Shift+Enter for newline</div>
    </form>
  );
}
