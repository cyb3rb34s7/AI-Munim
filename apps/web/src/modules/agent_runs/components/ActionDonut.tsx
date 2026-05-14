import { useMemo } from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { useThemeStore } from '@/shared/store/theme';
import { AgentAction, type AgentRunDecision } from '@/modules/agent_runs/api/client';

const LABELS: Record<AgentAction, string> = {
  [AgentAction.CONVERT_TO_PREPAID]: 'Convert to prepaid',
  [AgentAction.CONFIRMATION_CALL]: 'Confirmation call',
  [AgentAction.NO_ACTION]: 'No action',
};

function readTokenColor(name: string): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return raw ? `hsl(${raw})` : 'currentColor';
}

function useActionColors(): Record<AgentAction, string> {
  const resolvedTheme = useThemeStore((s) => s.resolvedTheme);
  return useMemo(
    () => ({
      [AgentAction.CONVERT_TO_PREPAID]: readTokenColor('--primary'),
      [AgentAction.CONFIRMATION_CALL]: readTokenColor('--warning'),
      [AgentAction.NO_ACTION]: readTokenColor('--fg-subtle'),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resolvedTheme],
  );
}

export function ActionDonut({ decisions }: { decisions: AgentRunDecision[] }) {
  const colors = useActionColors();
  const surfaceColor = useMemo(() => readTokenColor('--surface-elevated'), []);
  const borderColor = useMemo(() => readTokenColor('--border'), []);
  const fgColor = useMemo(() => readTokenColor('--fg'), []);

  const counts: Record<AgentAction, number> = {
    [AgentAction.CONVERT_TO_PREPAID]: 0,
    [AgentAction.CONFIRMATION_CALL]: 0,
    [AgentAction.NO_ACTION]: 0,
  };
  for (const d of decisions) {
    counts[d.action] += 1;
  }
  const data = (Object.keys(counts) as AgentAction[])
    .filter((action) => counts[action] > 0)
    .map((action) => ({ name: LABELS[action], value: counts[action], action }));

  if (data.length === 0) return null;

  return (
    <div className="h-[200px] w-full">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" innerRadius={56} outerRadius={84} paddingAngle={2}>
            {data.map((entry) => (
              <Cell key={entry.action} fill={colors[entry.action]} stroke="none" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: surfaceColor,
              border: `1px solid ${borderColor}`,
              borderRadius: 12,
              fontSize: 13,
              color: fgColor,
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
