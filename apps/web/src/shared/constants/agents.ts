export const AgentName = {
  RTO_MITIGATOR: 'rto_mitigator',
  DAILY_BRIEFING: 'daily_briefing',
} as const;
export type AgentName = (typeof AgentName)[keyof typeof AgentName];

const AGENT_LABEL: Record<AgentName, string> = {
  [AgentName.RTO_MITIGATOR]: 'RTO Risk Mitigator',
  [AgentName.DAILY_BRIEFING]: 'Daily Briefing',
};

export function agentDisplayName(name: string): string {
  return AGENT_LABEL[name as AgentName] ?? name;
}
