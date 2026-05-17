import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { triggerBriefing } from '@/modules/agent_runs/api/client';
import { ApiError } from '@/shared/api';
import { useAgentRunMetaStore } from '@/shared/store/agentRunMeta';
import type { Sector } from '@/shared/constants/sectors';

export function useTriggerBriefing() {
  const qc = useQueryClient();
  const setLastTriggeredRunId = useAgentRunMetaStore((s) => s.setLastTriggeredRunId);
  return useMutation({
    mutationFn: (sector: Sector) => triggerBriefing(sector),
    onSuccess: (run) => {
      setLastTriggeredRunId(run.run_log_id);
      toast.success('Briefing ready', {
        description: `${run.actions_proposed} action${run.actions_proposed === 1 ? '' : 's'} proposed.`,
      });
      qc.invalidateQueries({ queryKey: ['agent-runs'] });
    },
    onError: (error: Error) => {
      const traceId = error instanceof ApiError ? `trace: ${error.traceId}` : undefined;
      toast.error('Briefing failed', {
        description: traceId ? `${error.message}\n${traceId}` : error.message,
      });
    },
  });
}
