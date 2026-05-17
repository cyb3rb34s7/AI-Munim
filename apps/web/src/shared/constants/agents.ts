export const AgentName = {
  RTO_MITIGATOR: 'rto_mitigator',
} as const;
export type AgentName = (typeof AgentName)[keyof typeof AgentName];

const AGENT_LABEL: Record<AgentName, string> = {
  [AgentName.RTO_MITIGATOR]: 'RTO Risk Mitigator',
};

export function agentDisplayName(name: string): string {
  return AGENT_LABEL[name as AgentName] ?? name;
}
