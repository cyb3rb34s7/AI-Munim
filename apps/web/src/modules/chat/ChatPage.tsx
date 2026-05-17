import { useChat } from './hooks/useChat';
import { MessageList } from './components/MessageList';
import { ChatInput } from './components/ChatInput';
import { ApiError } from '@/shared/api';

const CHAT_ERROR_HEADLINE: Record<string, string> = {
  'chat.unverified_answer':
    "I couldn't deliver an answer I could fully back up against real rows. Try asking again, or rephrase — a slightly different angle often helps.",
  'chat.llm_unavailable':
    "The model isn't responding right now. Wait a moment and try again.",
  'chat.tool_failed':
    'Something went wrong while pulling your data. Try the question again.',
  'auth.unauthenticated': 'Your demo session has expired. Refresh to start a fresh one.',
};

function friendlyChatError(error: Error): { headline: string; traceId: string | null } {
  if (error instanceof ApiError) {
    const headline =
      CHAT_ERROR_HEADLINE[error.code] ??
      'Something unexpected happened on our side. Try asking again.';
    return { headline, traceId: error.traceId };
  }
  return {
    headline: "Couldn't reach the server. Check your connection and try again.",
    traceId: null,
  };
}

export function ChatPage() {
  const { messages, send, isPending, error } = useChat();

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col px-6 py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">Munim</h1>
        <p className="text-sm text-fg-muted">
          Your AI employee. Every answer is grounded in a real row from your store.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto pb-4">
        <MessageList messages={messages} isPending={isPending} onSuggest={send} />
        {error &&
          (() => {
            const { headline, traceId } = friendlyChatError(error);
            return (
              <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <div>{headline}</div>
                {traceId && (
                  <div className="mt-1.5 font-mono text-[10px] text-fg-subtle">
                    trace: {traceId}
                  </div>
                )}
              </div>
            );
          })()}
      </div>

      <div className="pt-2 pb-2">
        <ChatInput onSend={send} isPending={isPending} />
      </div>
    </div>
  );
}
