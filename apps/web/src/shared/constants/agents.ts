export const AgentName = {
  RTO_MITIGATOR: 'rto_mitigator',
} as const;
export type AgentName = (typeof AgentName)[keyof typeof AgentName];
