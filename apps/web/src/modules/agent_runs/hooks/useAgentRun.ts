import { useQuery } from '@tanstack/react-query';
import { fetchAgentRun } from '@/modules/agent_runs/api/client';

export function useAgentRun(runLogId: number | null) {
  return useQuery({
    queryKey: ['agent-run', runLogId],
    queryFn: () => fetchAgentRun(runLogId as number),
    enabled: runLogId !== null,
  });
}
