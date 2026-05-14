import { Loader2, Play } from 'lucide-react';
import { Button } from '@/shared/ui';
import { useTriggerAgent } from '@/modules/agent_runs/hooks/useTriggerAgent';
import { AgentName } from '@/shared/constants/agents';

export function TriggerAgentButton() {
  const mutation = useTriggerAgent(AgentName.RTO_MITIGATOR);
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
