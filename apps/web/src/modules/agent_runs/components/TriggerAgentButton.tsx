import { Loader2, Play } from 'lucide-react';
import { Button } from '@/shared/ui';
import { useTriggerAgent } from '@/modules/agent_runs/hooks/useTriggerAgent';

const AGENT_NAME = 'rto_mitigator';

export function TriggerAgentButton() {
  const mutation = useTriggerAgent(AGENT_NAME);
  return (
    <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
      {mutation.isPending ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Play className="h-4 w-4" />
      )}
      {mutation.isPending ? 'Running…' : 'Run agent now'}
    </Button>
  );
}
