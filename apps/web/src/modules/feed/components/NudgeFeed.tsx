import { motion } from 'framer-motion';
import { useAgentNudges } from '@/modules/feed/hooks/useAgentNudges';
import { NudgeCard } from './NudgeCard';
import { Skeleton } from '@/shared/ui';
import { stagger } from '@/shared/utils/motion';

export function NudgeFeed() {
  const { data, isLoading, error } = useAgentNudges();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-[112px] w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return <div className="text-sm text-destructive">Couldn't load nudges. Server unreachable.</div>;
  }

  if (!data?.items.length) {
    return (
      <div className="text-sm text-fg-muted">
        No agent runs yet. Trigger one from the Agents page.
      </div>
    );
  }

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="visible"
      className="flex flex-col gap-3"
    >
      {data.items.map((nudge) => (
        <NudgeCard key={nudge.run_log_id} nudge={nudge} />
      ))}
    </motion.div>
  );
}
