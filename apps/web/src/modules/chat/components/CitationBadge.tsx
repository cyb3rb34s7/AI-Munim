import { motion } from 'framer-motion';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui';
import { pulse } from '@/shared/utils/motion';
import type { RowCitation } from '@/modules/chat/api/client';

interface Props {
  citation: RowCitation;
}

export function CitationBadge({ citation }: Props) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.button
          type="button"
          initial={pulse.initial}
          animate={pulse.animate}
          className="inline-flex items-center align-baseline mx-0.5 px-1.5 py-0.5 rounded-md text-[11px] font-medium bg-accent text-accent-fg hover:bg-primary hover:text-primary-fg transition-colors"
        >
          {citation.id}
        </motion.button>
      </TooltipTrigger>
      <TooltipContent>
        <div className="text-xs">
          <div className="font-medium text-fg">{citation.entity_type}</div>
          <div className="text-fg-muted">
            {citation.source_system} · {citation.source_id}
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
