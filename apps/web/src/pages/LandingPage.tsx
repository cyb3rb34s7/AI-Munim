import { Link, Navigate } from 'react-router-dom';
import { MessageCircle, Workflow, Database, ExternalLink } from 'lucide-react';

import { Button } from '@/shared/ui';
import { useAuthContext } from '@/modules/auth';

const FEATURES = [
  {
    icon: Database,
    title: 'Universal data model',
    body: 'Shopify, Meta Ads, and Shiprocket land in one provenance-tagged store. Every row has a citation.',
  },
  {
    icon: MessageCircle,
    title: 'Grounded chat',
    body: 'Every number the LLM says comes with a [cite:id]. Hover to verify against the source row.',
  },
  {
    icon: Workflow,
    title: 'Deterministic agent',
    body: 'RTO Risk Mitigator scans COD orders nightly, scores, and proposes — auditable, reproducible.',
  },
];

export function LandingPage() {
  const { user, isLoading } = useAuthContext();
  if (isLoading) return null;
  if (user !== null) return <Navigate to="/chat" replace />;

  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-8 py-6">
        <div className="text-xl font-semibold tracking-tight">Munim</div>
        <a
          href="https://github.com/cyb3rb34s7/ai-munim"
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-2 text-sm text-fg-muted hover:text-fg"
        >
          <ExternalLink size={16} aria-hidden />
          GitHub
        </a>
      </header>

      <main className="mx-auto max-w-6xl px-8 pb-20">
        <section className="pt-12 pb-20 text-center">
          <h1 className="text-5xl font-semibold tracking-tight text-fg">
            Munim — your AI employee for D2C.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-fg-muted">
            One workspace for Shopify, Meta, and Shiprocket data. Grounded chat with citations, a
            deterministic risk-mitigation agent, three connectors behind one abstraction.
          </p>
          <div className="mt-10 flex items-center justify-center gap-3">
            <Button asChild size="lg">
              <Link to="/start">Try the live demo</Link>
            </Button>
          </div>
          <p className="mt-3 text-xs text-fg-muted">
            No sign-up. A private demo workspace is created when you click.
          </p>
        </section>

        <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border border-border bg-surface-elevated p-6"
            >
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <feature.icon size={20} aria-hidden />
              </div>
              <h2 className="mt-4 text-lg font-medium text-fg">{feature.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">{feature.body}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-8 py-6 text-xs text-fg-muted">
          Built as a hiring assignment. Honest limitations and tech defenses in the README.
        </div>
      </footer>
    </div>
  );
}
