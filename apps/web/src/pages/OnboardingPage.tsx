import { useEffect, useMemo, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, Check, Loader2, Megaphone, Plug, Truck } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { Button } from '@/shared/ui';
import { ApiError } from '@/shared/api';
import { useConnectors } from '@/modules/connectors/hooks/useConnectors';
import type { ConnectorView } from '@/modules/connectors/types/connector.types';
import { useOnboard, type OnboardingResult } from '@/modules/auth';

const CONNECTOR_STEPS = [
  {
    key: 'shopify',
    icon: Plug,
    name: 'Shopify',
    blurb: 'Orders, customers, fulfilment status.',
    countLabel: (r: OnboardingResult) => `Synced ${r.shopify_rows} orders`,
  },
  {
    key: 'meta_ads',
    icon: Megaphone,
    name: 'Meta Ads',
    blurb: 'Daily insights per ad set — spend, clicks, conversions.',
    countLabel: (r: OnboardingResult) => `Synced ${r.meta_ads_rows} insight rows`,
  },
  {
    key: 'shiprocket',
    icon: Truck,
    name: 'Shiprocket',
    blurb: 'Shipment lifecycle status — RTO history powers the agent.',
    countLabel: (r: OnboardingResult) => `Synced ${r.shiprocket_rows} shipments`,
  },
] as const satisfies ReadonlyArray<{
  key: 'shopify' | 'meta_ads' | 'shiprocket';
  icon: LucideIcon;
  name: string;
  blurb: string;
  countLabel: (r: OnboardingResult) => string;
}>;

const STEP_DELAY_MS = 700;

type StepStatus = 'idle' | 'syncing' | 'done';

function isAlreadyOnboarded(connectors: ConnectorView[] | undefined): boolean {
  if (!connectors) return false;
  const required: Array<'shopify' | 'meta_ads' | 'shiprocket'> = [
    'shopify',
    'meta_ads',
    'shiprocket',
  ];
  return required.every((name) => {
    const view = connectors.find((c) => c.name === name);
    return view !== undefined && view.status === 'demo' && view.last_sync_at !== null;
  });
}

function recordCountsToResult(connectors: ConnectorView[]): OnboardingResult {
  function sum(name: 'shopify' | 'meta_ads' | 'shiprocket'): number {
    const view = connectors.find((c) => c.name === name);
    if (!view) return 0;
    return view.record_counts.reduce((acc, entry) => acc + entry.count, 0);
  }
  return {
    shopify_rows: sum('shopify'),
    meta_ads_rows: sum('meta_ads'),
    shiprocket_rows: sum('shiprocket'),
  };
}

export function OnboardingPage() {
  const { connectors, isLoading } = useConnectors();
  const onboard = useOnboard();

  const [statuses, setStatuses] = useState<Record<string, StepStatus>>({
    shopify: 'idle',
    meta_ads: 'idle',
    shiprocket: 'idle',
  });
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const alreadyOnboarded = useMemo(() => isAlreadyOnboarded(connectors), [connectors]);

  useEffect(() => {
    if (alreadyOnboarded && connectors && result === null) {
      setStatuses({ shopify: 'done', meta_ads: 'done', shiprocket: 'done' });
      setResult(recordCountsToResult(connectors));
    }
  }, [alreadyOnboarded, connectors, result]);

  const allDone =
    statuses.shopify === 'done' &&
    statuses.meta_ads === 'done' &&
    statuses.shiprocket === 'done';

  function handleConnectClick() {
    setError(null);
    onboard.mutate(undefined, {
      onSuccess: (data) => {
        setResult(data);
        runSequentialReveal();
      },
      onError: (err) => {
        const message =
          err instanceof ApiError ? err.message : 'Could not load demo data. Try again.';
        setError(message);
        setStatuses({ shopify: 'idle', meta_ads: 'idle', shiprocket: 'idle' });
      },
    });
    setStatuses({ shopify: 'syncing', meta_ads: 'idle', shiprocket: 'idle' });
  }

  function runSequentialReveal() {
    const sequence: Array<'shopify' | 'meta_ads' | 'shiprocket'> = [
      'shopify',
      'meta_ads',
      'shiprocket',
    ];
    sequence.forEach((key, index) => {
      const startAt = index * STEP_DELAY_MS;
      const completeAt = startAt + STEP_DELAY_MS;
      const nextKey = sequence[index + 1];
      window.setTimeout(() => {
        setStatuses((prev) => ({ ...prev, [key]: 'syncing' }));
      }, startAt);
      window.setTimeout(() => {
        setStatuses((prev) => ({
          ...prev,
          [key]: 'done',
          ...(nextKey ? { [nextKey]: 'syncing' as StepStatus } : {}),
        }));
      }, completeAt);
    });
  }

  if (isLoading) return null;
  if (!isLoading && connectors === undefined) {
    // Connectors fetch errored — we still need a session to be here, so this
    // is most likely a transient backend hiccup. Send the user to /chat,
    // which is also fail-soft (empty state) if they truly have no data.
    return <Navigate to="/chat" replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-6 text-fg">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-2xl space-y-6 rounded-xl border border-border bg-surface-elevated p-8 shadow-sm"
      >
        <header className="space-y-3">
          <span className="inline-flex items-center rounded-full border border-border bg-surface-subtle px-2.5 py-0.5 text-xs font-medium text-fg-muted">
            Demo mode
          </span>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">
            Set up your demo workspace
          </h1>
          <p className="text-sm text-fg-muted">
            We&rsquo;ll pre-fill realistic data from three connectors so you can explore right
            away. In production, each connector goes through its own auth flow.
          </p>
        </header>

        <ul className="space-y-3">
          {CONNECTOR_STEPS.map((step) => {
            const status = statuses[step.key];
            const Icon = step.icon;
            return (
              <li
                key={step.key}
                className="flex items-center gap-4 rounded-lg border border-border bg-surface p-4"
              >
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-surface-subtle text-fg-muted">
                  <Icon size={18} aria-hidden />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-fg">{step.name}</div>
                  <div className="text-xs text-fg-muted">{step.blurb}</div>
                </div>
                <div className="w-44 shrink-0 text-right">
                  <AnimatePresence mode="wait">
                    {status === 'idle' && (
                      <motion.span
                        key="idle"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="text-xs text-fg-subtle"
                      >
                        Ready
                      </motion.span>
                    )}
                    {status === 'syncing' && (
                      <motion.span
                        key="syncing"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="inline-flex items-center gap-1.5 text-xs text-fg-muted"
                      >
                        <Loader2 size={14} className="animate-spin" aria-hidden />
                        Connecting…
                      </motion.span>
                    )}
                    {status === 'done' && (
                      <motion.span
                        key="done"
                        initial={{ opacity: 0, x: 8 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        className="inline-flex items-center gap-1.5 text-xs font-medium text-success"
                      >
                        <Check size={14} aria-hidden />
                        {result ? step.countLabel(result) : 'Synced'}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>
              </li>
            );
          })}
        </ul>

        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex items-center justify-between gap-3 pt-2">
          <Link
            to="/chat"
            className="text-xs text-fg-subtle hover:text-fg-muted underline-offset-2 hover:underline"
          >
            Skip — go to chat
          </Link>
          {allDone ? (
            <Button asChild>
              <Link to="/chat" className="inline-flex items-center gap-1.5">
                Go to chat
                <ArrowRight size={14} aria-hidden />
              </Link>
            </Button>
          ) : (
            <Button onClick={handleConnectClick} disabled={onboard.isPending}>
              {onboard.isPending || statuses.shopify === 'syncing' ? 'Connecting…' : 'Connect demo data'}
            </Button>
          )}
        </div>
      </motion.div>
    </div>
  );
}
