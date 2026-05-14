import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { AgentAction, type AgentRunDecision } from '@/modules/agent_runs/api/client';

const COLORS: Record<AgentAction, string> = {
  [AgentAction.CONVERT_TO_PREPAID]: 'hsl(263 70% 60%)',
  [AgentAction.CONFIRMATION_CALL]: 'hsl(38 92% 50%)',
  [AgentAction.NO_ACTION]: 'hsl(263 10% 60%)',
};

const LABELS: Record<AgentAction, string> = {
  [AgentAction.CONVERT_TO_PREPAID]: 'Convert to prepaid',
  [AgentAction.CONFIRMATION_CALL]: 'Confirmation call',
  [AgentAction.NO_ACTION]: 'No action',
};

export function ActionDonut({ decisions }: { decisions: AgentRunDecision[] }) {
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
              <Cell key={entry.action} fill={COLORS[entry.action]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: 'hsl(var(--surface))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 12,
              fontSize: 13,
              color: 'hsl(var(--fg))',
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
