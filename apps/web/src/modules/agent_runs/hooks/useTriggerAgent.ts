import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { triggerAgent } from '@/modules/agent_runs/api/client';

export function useTriggerAgent(name: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => triggerAgent(name),
    onSuccess: (run) => {
      toast.success(`Agent ran`, {
        description: `${run.orders_scanned} orders scanned, ${run.actions_proposed} action${run.actions_proposed === 1 ? '' : 's'} proposed.`,
      });
      qc.invalidateQueries({ queryKey: ['agent-runs'] });
    },
    onError: (error: Error) => {
      toast.error('Agent run failed', { description: error.message });
    },
  });
}
