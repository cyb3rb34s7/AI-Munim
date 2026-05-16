import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { Button } from '@/shared/components';
import { ApiError } from '@/shared/api';

import { useStartDemo } from '../hooks/useAuth';

const MAX_DISPLAY_NAME = 80;

export function StartDemoForm() {
  const [displayName, setDisplayName] = useState('');
  const navigate = useNavigate();
  const { mutate, isPending } = useStartDemo();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = displayName.trim();
    mutate(
      { display_name: trimmed || undefined },
      {
        onSuccess: () => {
          navigate('/chat');
        },
        onError: (error) => {
          const message = error instanceof ApiError ? error.message : 'Could not start demo.';
          toast.error(message);
        },
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-2 text-sm">
        <span className="text-fg-muted">Display name (optional)</span>
        <input
          type="text"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value.slice(0, MAX_DISPLAY_NAME))}
          maxLength={MAX_DISPLAY_NAME}
          placeholder="Demo User"
          autoFocus
          className="h-10 rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg outline-none transition-colors focus:border-primary"
        />
      </label>
      <Button type="submit" loading={isPending}>
        Start demo
      </Button>
    </form>
  );
}
