import { NudgeFeed } from '@/modules/feed/components/NudgeFeed';

export function FeedPanel() {
  return (
    <aside className="hidden lg:flex h-screen w-[360px] flex-col border-l border-border bg-surface-subtle">
      <div className="border-b border-border p-5">
        <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle">Activity</div>
        <div className="text-lg font-semibold tracking-tight text-fg">Agent nudges</div>
        <div className="text-sm text-fg-muted">Recent proposals from your AI employee.</div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <NudgeFeed />
      </div>
    </aside>
  );
}
