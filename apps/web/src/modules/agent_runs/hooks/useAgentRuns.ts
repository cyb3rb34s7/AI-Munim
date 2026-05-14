import { useQuery } from '@tanstack/react-query';
import { fetchAgentRuns } from '@/modules/agent_runs/api/client';

export function useAgentRuns(limit = 50) {
  return useQuery({
    queryKey: ['agent-runs', { limit }],
    queryFn: () => fetchAgentRuns({ limit }),
    refetchOnWindowFocus: true,
  });
}
