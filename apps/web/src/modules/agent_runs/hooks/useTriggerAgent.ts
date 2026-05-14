import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { triggerAgent } from '@/modules/agent_runs/api/client';
import { ApiError } from '@/shared/api';
import { useAgentRunMetaStore } from '@/shared/store/agentRunMeta';
import type { AgentName } from '@/shared/constants/agents';

export function useTriggerAgent(name: AgentName) {
  const qc = useQueryClient();
  const setLastTriggeredRunId = useAgentRunMetaStore((s) => s.setLastTriggeredRunId);
  return useMutation({
    mutationFn: () => triggerAgent(name),
    onSuccess: (run) => {
      setLastTriggeredRunId(run.run_log_id);
      toast.success('Agent ran', {
        description: `${run.orders_scanned} orders scanned, ${run.actions_proposed} action${run.actions_proposed === 1 ? '' : 's'} proposed.`,
      });
      qc.invalidateQueries({ queryKey: ['agent-runs'] });
    },
    onError: (error: Error) => {
      const traceId = error instanceof ApiError ? `trace: ${error.traceId}` : undefined;
      toast.error('Agent run failed', {
        description: traceId ? `${error.message}\n${traceId}` : error.message,
      });
    },
  });
}
