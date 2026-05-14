import { create } from 'zustand';

interface AgentRunMetaState {
  lastTriggeredRunId: number | null;
  setLastTriggeredRunId: (id: number) => void;
}

export const useAgentRunMetaStore = create<AgentRunMetaState>((set) => ({
  lastTriggeredRunId: null,
  setLastTriggeredRunId: (id) => set({ lastTriggeredRunId: id }),
}));
