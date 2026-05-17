import { z } from 'zod';
import { apiGet, apiPost } from '@/shared/api';

export const AgentAction = {
  CONVERT_TO_PREPAID: 'convert_to_prepaid',
  CONFIRMATION_CALL: 'confirmation_call',
  NO_ACTION: 'no_action',
} as const;
export type AgentAction = (typeof AgentAction)[keyof typeof AgentAction];

const agentActionSchema = z.enum([
  AgentAction.CONVERT_TO_PREPAID,
  AgentAction.CONFIRMATION_CALL,
  AgentAction.NO_ACTION,
]);

const agentRunSummarySchema = z.object({
  run_log_id: z.number(),
  run_id: z.string(),
  agent: z.string(),
  orders_scanned: z.number(),
  actions_proposed: z.number(),
  started_at: z.string(),
  finished_at: z.string(),
});

const agentRunDecisionSchema = z.object({
  record_id: z.number(),
  source_id: z.string(),
  score: z.number(),
  action: agentActionSchema,
  estimated_inr_saved: z.string(),
  signal_scores: z.record(z.string(), z.number()),
  signal_diagnostics: z.record(z.string(), z.record(z.string(), z.unknown())),
  weights: z.record(z.string(), z.number()),
  reasoning: z.string(),
});

const rowCitationSchema = z.object({
  record_id: z.number(),
  entity_type: z.string(),
  source_system: z.string(),
  source_id: z.string(),
  excerpt: z.record(z.string(), z.unknown()),
});

const proposedActionSchema = z.object({
  action_type: z.string(),
  reasoning: z.string(),
  evidence_record_ids: z.array(z.number()),
});

const agentRunDetailSchema = agentRunSummarySchema.extend({
  decisions: z.array(agentRunDecisionSchema),
  sector: z.string().nullable().optional(),
  narrative: z.string().nullable().optional(),
  proposed_actions: z.array(proposedActionSchema).nullable().optional(),
  citations: z.array(rowCitationSchema).nullable().optional(),
});

const listResponseSchema = z.object({ items: z.array(agentRunSummarySchema) });

const triggerResponseSchema = z.object({ run: agentRunSummarySchema });

export type AgentRunSummary = z.infer<typeof agentRunSummarySchema>;
export type AgentRunDecision = z.infer<typeof agentRunDecisionSchema>;
export type AgentRunDetail = z.infer<typeof agentRunDetailSchema>;
export type ProposedAction = z.infer<typeof proposedActionSchema>;
export type RowCitation = z.infer<typeof rowCitationSchema>;

export async function fetchAgentRuns(params: { limit?: number } = {}) {
  const limit = params.limit ?? 50;
  const { data } = await apiGet('agent-runs', listResponseSchema, {
    searchParams: { limit },
  });
  return data;
}

export async function fetchAgentRun(runLogId: number) {
  const { data } = await apiGet(`agent-runs/${runLogId}`, agentRunDetailSchema);
  return data;
}

export async function triggerAgent(name: string) {
  const { data } = await apiPost(`agents/${name}/run`, triggerResponseSchema);
  return data.run;
}

export async function triggerBriefing(sector: string) {
  const { data } = await apiPost(`agents/daily_briefing/run`, triggerResponseSchema, {
    searchParams: { sector },
  });
  return data.run;
}
