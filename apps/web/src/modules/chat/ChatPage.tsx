import { useChat } from './hooks/useChat';
import { MessageList } from './components/MessageList';
import { ChatInput } from './components/ChatInput';

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
        {error && (
          <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error.message}
          </div>
        )}
      </div>

      <div className="pt-2 pb-2">
        <ChatInput onSend={send} isPending={isPending} />
      </div>
    </div>
  );
}
