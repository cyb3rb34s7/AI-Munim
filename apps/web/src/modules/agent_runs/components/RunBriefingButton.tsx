import { useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { Button } from '@/shared/ui';
import { useTriggerBriefing } from '@/modules/agent_runs/hooks/useTriggerBriefing';
import { SECTOR_LABEL, SECTOR_OPTIONS, Sector } from '@/shared/constants/sectors';

export function RunBriefingButton() {
  const [sector, setSector] = useState<Sector>(Sector.FASHION);
  const mutation = useTriggerBriefing();

  return (
    <div className="flex items-end gap-2">
      <label className="flex flex-col gap-1 text-xs text-fg-subtle">
        <span className="uppercase tracking-wider">Sector</span>
        <select
          value={sector}
          onChange={(e) => setSector(e.target.value as Sector)}
          disabled={mutation.isPending}
          className="h-9 rounded-md border border-border bg-surface px-2.5 text-sm text-fg focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
        >
          {SECTOR_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {SECTOR_LABEL[s]}
            </option>
          ))}
        </select>
      </label>
      <Button
        variant="secondary"
        onClick={() => mutation.mutate(sector)}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
        {mutation.isPending ? 'Composing…' : 'Run daily briefing'}
      </Button>
    </div>
  );
}
