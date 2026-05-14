import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { fetchAgentRuns, type AgentRunSummary } from '@/modules/agent_runs';
import { useAgentRunMetaStore } from '@/shared/store/agentRunMeta';

const POLL_MS = 30_000;

export function useAgentNudges() {
  const navigate = useNavigate();
  const lastSeenId = useRef<number | null>(null);
  const lastTriggeredRunId = useAgentRunMetaStore((s) => s.lastTriggeredRunId);

  const query = useQuery({
    queryKey: ['agent-runs', { limit: 10 }],
    queryFn: () => fetchAgentRuns({ limit: 10 }),
    refetchInterval: POLL_MS,
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    const items = query.data?.items;
    if (!items?.length) return;
    const newest = items[0];
    const isNewToFeed =
      lastSeenId.current !== null && newest.run_log_id > lastSeenId.current;
    const wasUserTriggered = newest.run_log_id === lastTriggeredRunId;
    if (isNewToFeed && !wasUserTriggered) {
      toast(
        `Agent proposed ${newest.actions_proposed} action${newest.actions_proposed === 1 ? '' : 's'}`,
        {
          description: `${newest.orders_scanned} orders scanned by ${newest.agent}.`,
          action: {
            label: 'Review',
            onClick: () => navigate(`/agents?run=${newest.run_log_id}`),
          },
        },
      );
    }
    lastSeenId.current = newest.run_log_id;
  }, [query.data, navigate, lastTriggeredRunId]);

  return query;
}

export type { AgentRunSummary };
