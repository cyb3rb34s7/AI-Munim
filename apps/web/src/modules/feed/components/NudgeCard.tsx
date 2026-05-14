import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { Button, Card } from '@/shared/ui';
import type { AgentRunSummary } from '@/modules/feed/hooks/useAgentNudges';
import { fadeUp } from '@/shared/utils/motion';

interface Props {
  nudge: AgentRunSummary;
}

export function NudgeCard({ nudge }: Props) {
  const navigate = useNavigate();
  const hasAction = nudge.actions_proposed > 0;
  return (
    <motion.div variants={fadeUp}>
      <Card className="p-4 flex flex-col gap-3 bg-surface">
        <div className="flex items-start gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-accent text-accent-fg shrink-0">
            <Sparkles className="h-4 w-4" />
          </div>
          <div className="flex flex-col gap-0.5 min-w-0">
            <div className="text-sm font-medium text-fg truncate">
              {hasAction
                ? `${nudge.actions_proposed} action${nudge.actions_proposed === 1 ? '' : 's'} proposed`
                : 'No actions proposed'}
            </div>
            <div className="text-xs text-fg-muted">
              {nudge.orders_scanned} orders scanned · {new Date(nudge.finished_at).toLocaleString()}
            </div>
          </div>
        </div>
        <Button
          variant={hasAction ? 'primary' : 'secondary'}
          size="sm"
          onClick={() => navigate(`/agents?run=${nudge.run_log_id}`)}
          className="w-full"
        >
          {hasAction ? 'Review proposals' : 'View run'}
        </Button>
      </Card>
    </motion.div>
  );
}
