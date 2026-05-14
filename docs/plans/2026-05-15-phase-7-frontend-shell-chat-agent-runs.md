# Phase 7 — Frontend Shell + Chat + Agent Runs Implementation Plan

> **For agentic workers:** ONE subagent dispatch for the whole phase (`CLAUDE.md §3`). 8 tasks top-to-bottom, commit per task per the plan, report DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED. Use `superpowers:subagent-driven-development`.
>
> **Comment discipline (user feedback, repeat-offender risk):** default to NO comments. Only a comment when WHY is genuinely non-obvious (a hidden constraint, a workaround). NEVER task-referential comments — no "Phase 7 reviewer caught this," no "from the plan," no "added for the brief." Never narrate what well-named code does.
>
> **Vibe (non-negotiable):** sophisticated, professional, calm. NOT vibe-coded. Inspirations from the user: Agent.ai-style dashboard (slim icon sidebar → expanding nav → main → right feed panel; rounded cards 16-20px; lavender accent on dark) AND an iPad-style chat surface with a soft AI-persona avatar. Smooth transitions and a persistent agent-nudge feed are part of the deliverable.

**Goal:** Ship the frontend for the two scored axes of the brief — Chat (with citation badges, live against `POST /chat/messages`) and Agent Runs (with detail drawer + manual trigger + action distribution donut) — inside a polished app shell with a persistent agent-nudge feed in the right column. Light + dark themes. Smooth, restrained motion. Existing Connectors and Records pages inherit the new shell automatically.

**Architecture:**
- **Design tokens** rewritten in `src/styles/globals.css` with a lavender/violet palette (light + dark), expanded scale (surface, surface-elevated, ring, accent, accent-foreground, primary, primary-foreground, success/warning/destructive, coral pop for agent-nudge highlights), and rounded radii (`md=14px`, `lg=20px`, `xl=28px`).
- **shadcn-style UI primitives** added under `src/shared/ui/` (manually adapted to our `@theme inline` tokens, not the shadcn CLI — Tailwind v4 + our existing setup) on top of Radix headless components. `cva` + `clsx` + `tailwind-merge` are the patterning primitives.
- **Motion** via Framer Motion: page transitions (`AnimatePresence`), card stagger on mount, citation badge pulse on first appearance, toast slide-in for agent nudges.
- **Charts** via Recharts: action-distribution donut on agent run detail.
- **Notifications** via Sonner: agent nudges that arrive between polls fire a slide-in toast with a Review action.
- **App shell** in `src/shared/layout/` — `AppShell.tsx` (3-column grid: `Sidebar | Main | FeedPanel`), `Sidebar.tsx` (icon column + collapsible label column, brand at top, user/theme at bottom), `FeedPanel.tsx` (renders the `feed` module's `<NudgeFeed />`).
- **New modules** under `src/modules/`:
  - `chat/` — `api/`, `components/`, `hooks/`, `types/`, `ChatPage.tsx`.
  - `agent_runs/` — `api/`, `components/`, `hooks/`, `types/`, `AgentRunsPage.tsx`.
  - `feed/` — `api/`, `components/`, `hooks/`, `FeedPanel.tsx` (rendered by `AppShell`).
- **Routing** in `src/router.tsx`: `/` redirects to `/chat`; `/chat`, `/agents`, `/connectors`, `/records` are routes.
- **State boundary** unchanged from `docs/conventions.md`: server state is TanStack Query, UI state is Zustand. Don't mix them.

**Tech stack additions (deps):**
- `framer-motion@^12`
- `recharts@^2`
- `sonner@^1.5`
- `lucide-react@^0.460`
- `class-variance-authority@^0.7`
- `clsx@^2`
- `tailwind-merge@^2`
- Radix headless: `@radix-ui/react-dialog`, `@radix-ui/react-scroll-area`, `@radix-ui/react-avatar`, `@radix-ui/react-separator`, `@radix-ui/react-tooltip`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-slot`

**Out of scope (deliberate):**
- Home dashboard page with KPI cards — user chose "Chat + Agent Runs + Shell" scope. Connectors and Records inherit the new shell but their internals don't get rebuilt.
- Streaming chat (SSE). Chat is request/response; the request takes ~1-2s with OpenAI gpt-4o-mini. Acceptable for v0; a typing indicator covers the gap.
- Persistent chat history. Per Phase 5 decision (Option A), chat is stateless — each `POST /chat/messages` is a fresh prompt. The UI keeps an in-memory message list for the current session only.
- Per-decision RunLog rows. Detail drawer renders the per-order decisions inline from `detail_json`.
- Cron-fired agent runs in the feed. Nudges are derived from `GET /agent-runs?limit=10` (polled every 30s); manual trigger lives on the Agent Runs page.
- Mobile/tablet layouts. v0 is desktop-first. The shell collapses gracefully at 1024px but isn't tuned below that.

---

## File map

**New files:**
- `apps/web/src/styles/globals.css` (rewrite — lavender palette + expanded tokens)
- `apps/web/src/shared/ui/index.ts`
- `apps/web/src/shared/ui/button.tsx`
- `apps/web/src/shared/ui/card.tsx`
- `apps/web/src/shared/ui/sheet.tsx` (Radix Dialog as side sheet)
- `apps/web/src/shared/ui/scroll-area.tsx`
- `apps/web/src/shared/ui/avatar.tsx`
- `apps/web/src/shared/ui/badge.tsx`
- `apps/web/src/shared/ui/separator.tsx`
- `apps/web/src/shared/ui/tooltip.tsx`
- `apps/web/src/shared/ui/skeleton.tsx`
- `apps/web/src/shared/ui/sonner.tsx`
- `apps/web/src/shared/utils/cn.ts`
- `apps/web/src/shared/utils/motion.ts` (shared motion variants)
- `apps/web/src/shared/layout/AppShell.tsx` (replaces existing — see Task 3)
- `apps/web/src/shared/layout/Sidebar.tsx`
- `apps/web/src/shared/layout/FeedPanel.tsx`
- `apps/web/src/modules/chat/api/client.ts`
- `apps/web/src/modules/chat/types/index.ts`
- `apps/web/src/modules/chat/hooks/useChat.ts`
- `apps/web/src/modules/chat/components/MessageList.tsx`
- `apps/web/src/modules/chat/components/MessageBubble.tsx`
- `apps/web/src/modules/chat/components/CitationBadge.tsx`
- `apps/web/src/modules/chat/components/ChatInput.tsx`
- `apps/web/src/modules/chat/components/ChatAvatar.tsx`
- `apps/web/src/modules/chat/ChatPage.tsx`
- `apps/web/src/modules/agent_runs/api/client.ts`
- `apps/web/src/modules/agent_runs/types/index.ts`
- `apps/web/src/modules/agent_runs/hooks/useAgentRuns.ts`
- `apps/web/src/modules/agent_runs/hooks/useTriggerAgent.ts`
- `apps/web/src/modules/agent_runs/components/RunsTable.tsx`
- `apps/web/src/modules/agent_runs/components/RunDetailSheet.tsx`
- `apps/web/src/modules/agent_runs/components/ActionDonut.tsx`
- `apps/web/src/modules/agent_runs/components/TriggerAgentButton.tsx`
- `apps/web/src/modules/agent_runs/AgentRunsPage.tsx`
- `apps/web/src/modules/feed/components/NudgeFeed.tsx`
- `apps/web/src/modules/feed/components/NudgeCard.tsx`
- `apps/web/src/modules/feed/hooks/useAgentNudges.ts`

**Modified files:**
- `apps/web/package.json` (deps)
- `apps/web/src/router.tsx` (add `/chat`, `/agents`; redirect `/` → `/chat`)
- `apps/web/src/main.tsx` (mount Sonner toaster)
- `apps/web/src/modules/health/**` and `apps/web/src/modules/connectors/**` and `apps/web/src/modules/records/**` — minimal updates only to swap legacy `Card`/`Button` imports for the new `shared/ui` primitives where the visual fidelity gap is obvious. NO behavior changes. NO internal rebuilds.

**Deleted (replaced):**
- `apps/web/src/shared/components/AppShell.tsx` (replaced by `shared/layout/AppShell.tsx`)
- `apps/web/src/shared/components/Button.tsx`, `Card.tsx` (replaced by `shared/ui/button.tsx`, `card.tsx`)
- Update `apps/web/src/shared/components/index.ts` to re-export the new locations OR have callers import from `shared/ui` directly. Prefer the latter — fewer indirections.

---

## Task 1 — Deps + design tokens + utilities

**Files:** `apps/web/package.json`, `apps/web/src/styles/globals.css`, `apps/web/src/shared/utils/cn.ts`, `apps/web/src/shared/utils/motion.ts`.

- [ ] **Step 1:** Install deps from `apps/web/`:

```
pnpm add framer-motion recharts sonner lucide-react class-variance-authority clsx tailwind-merge
pnpm add @radix-ui/react-dialog @radix-ui/react-scroll-area @radix-ui/react-avatar @radix-ui/react-separator @radix-ui/react-tooltip @radix-ui/react-dropdown-menu @radix-ui/react-slot
```

- [ ] **Step 2:** Rewrite `src/styles/globals.css` with the expanded token system:

```css
@import 'tailwindcss';

@custom-variant dark (&:where(.dark, .dark *));

:root {
  /* Surfaces */
  --bg: 270 30% 99%;
  --surface: 0 0% 100%;
  --surface-elevated: 270 25% 98%;
  --surface-subtle: 270 20% 96%;
  --sidebar-bg: 263 35% 8%;
  --sidebar-fg: 270 20% 92%;
  --sidebar-muted: 270 10% 62%;
  --sidebar-hover: 263 30% 14%;

  /* Text */
  --fg: 263 25% 13%;
  --fg-muted: 263 10% 42%;
  --fg-subtle: 263 8% 58%;

  /* Borders + rings */
  --border: 270 20% 92%;
  --border-strong: 270 18% 86%;
  --ring: 263 70% 60%;

  /* Brand + accents */
  --primary: 263 70% 60%;
  --primary-fg: 0 0% 100%;
  --primary-hover: 263 70% 54%;
  --accent: 263 70% 95%;
  --accent-fg: 263 70% 30%;

  /* Semantic */
  --success: 152 55% 42%;
  --warning: 38 92% 50%;
  --destructive: 0 70% 56%;
  --pop: 14 90% 66%;

  /* Radii */
  --r-sm: 8px;
  --r-md: 14px;
  --r-lg: 20px;
  --r-xl: 28px;
}

.dark {
  --bg: 263 28% 6%;
  --surface: 263 22% 9%;
  --surface-elevated: 263 22% 12%;
  --surface-subtle: 263 18% 11%;
  --sidebar-bg: 263 35% 5%;
  --sidebar-fg: 270 18% 92%;
  --sidebar-muted: 270 12% 60%;
  --sidebar-hover: 263 30% 12%;

  --fg: 270 18% 95%;
  --fg-muted: 270 10% 65%;
  --fg-subtle: 270 8% 50%;

  --border: 263 18% 18%;
  --border-strong: 263 18% 24%;
  --ring: 263 80% 72%;

  --primary: 263 80% 70%;
  --primary-fg: 263 30% 10%;
  --primary-hover: 263 80% 74%;
  --accent: 263 50% 20%;
  --accent-fg: 263 90% 92%;

  --success: 152 60% 55%;
  --warning: 38 92% 60%;
  --destructive: 0 72% 65%;
  --pop: 14 92% 72%;
}

@theme inline {
  --color-bg: hsl(var(--bg));
  --color-surface: hsl(var(--surface));
  --color-surface-elevated: hsl(var(--surface-elevated));
  --color-surface-subtle: hsl(var(--surface-subtle));
  --color-sidebar-bg: hsl(var(--sidebar-bg));
  --color-sidebar-fg: hsl(var(--sidebar-fg));
  --color-sidebar-muted: hsl(var(--sidebar-muted));
  --color-sidebar-hover: hsl(var(--sidebar-hover));

  --color-fg: hsl(var(--fg));
  --color-fg-muted: hsl(var(--fg-muted));
  --color-fg-subtle: hsl(var(--fg-subtle));

  --color-border: hsl(var(--border));
  --color-border-strong: hsl(var(--border-strong));
  --color-ring: hsl(var(--ring));

  --color-primary: hsl(var(--primary));
  --color-primary-fg: hsl(var(--primary-fg));
  --color-primary-hover: hsl(var(--primary-hover));
  --color-accent: hsl(var(--accent));
  --color-accent-fg: hsl(var(--accent-fg));

  --color-success: hsl(var(--success));
  --color-warning: hsl(var(--warning));
  --color-destructive: hsl(var(--destructive));
  --color-pop: hsl(var(--pop));

  --radius-sm: var(--r-sm);
  --radius-md: var(--r-md);
  --radius-lg: var(--r-lg);
  --radius-xl: var(--r-xl);

  --font-sans:
    'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, 'Cascadia Code', monospace;
}

@layer base {
  *,
  *::before,
  *::after {
    border-color: hsl(var(--border));
  }
  html {
    color-scheme: light;
  }
  html.dark {
    color-scheme: dark;
  }
  body {
    @apply bg-bg text-fg font-sans antialiased;
    min-height: 100vh;
  }
  *:focus-visible {
    @apply outline-none ring-2 ring-ring ring-offset-2 ring-offset-bg;
  }
}
```

- [ ] **Step 3:** Create `src/shared/utils/cn.ts`:

```typescript
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 4:** Create `src/shared/utils/motion.ts`:

```typescript
import type { Variants } from 'framer-motion';

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.16, 1, 0.3, 1] } },
};

export const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.04, delayChildren: 0.04 } },
};

export const slideInRight: Variants = {
  hidden: { opacity: 0, x: 16 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.28, ease: [0.16, 1, 0.3, 1] } },
};

export const pulse = {
  initial: { scale: 1, opacity: 0 },
  animate: {
    scale: [0.95, 1.04, 1],
    opacity: [0, 1, 1],
    transition: { duration: 0.45, ease: 'easeOut' },
  },
};
```

- [ ] **Step 5:** Sanity-check the build picks up new tokens:

```
pnpm typecheck
pnpm lint
pnpm build
```

Expected: no errors. The build won't visually exercise the tokens yet — that comes in Task 2.

- [ ] **Step 6:** Commit.

```
git add apps/web/package.json apps/web/pnpm-lock.yaml apps/web/src/styles/globals.css apps/web/src/shared/utils/
git commit -m "feat(web): lavender token system, motion deps, cn util"
```

---

## Task 2 — Shared UI primitives (shadcn-style on Radix)

**Files:** `apps/web/src/shared/ui/*.tsx`, `apps/web/src/shared/ui/index.ts`.

These are minimal, opinionated React components built on Radix headless + Tailwind. They are the only place where button/card/dialog/etc styling lives — feature components compose these, never restyle them from scratch.

- [ ] **Step 1:** `src/shared/ui/button.tsx`:

```tsx
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/shared/utils/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-[background-color,box-shadow,transform] duration-150 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]',
  {
    variants: {
      variant: {
        primary:
          'bg-primary text-primary-fg shadow-sm hover:bg-primary-hover',
        secondary:
          'bg-surface-elevated text-fg border border-border hover:bg-surface-subtle',
        ghost: 'text-fg hover:bg-surface-elevated',
        destructive: 'bg-destructive text-white hover:opacity-90',
        pop: 'bg-pop text-white hover:opacity-90',
      },
      size: {
        sm: 'h-8 px-3',
        md: 'h-10 px-4',
        lg: 'h-11 px-5 text-base',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    );
  },
);
Button.displayName = 'Button';
```

- [ ] **Step 2:** `src/shared/ui/card.tsx`:

```tsx
import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '@/shared/utils/cn';

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'rounded-lg border border-border bg-surface shadow-sm',
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = 'Card';

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('flex flex-col gap-1.5 p-6 pb-3', className)} {...props} />
  ),
);
CardHeader.displayName = 'CardHeader';

export const CardTitle = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('text-lg font-semibold tracking-tight text-fg', className)} {...props} />
  ),
);
CardTitle.displayName = 'CardTitle';

export const CardDescription = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('text-sm text-fg-muted', className)} {...props} />
  ),
);
CardDescription.displayName = 'CardDescription';

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('p-6 pt-3', className)} {...props} />
  ),
);
CardContent.displayName = 'CardContent';
```

- [ ] **Step 3:** `src/shared/ui/sheet.tsx` (side drawer, used for run detail):

```tsx
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { forwardRef, type ComponentPropsWithoutRef, type HTMLAttributes } from 'react';
import { cn } from '@/shared/utils/cn';

export const Sheet = Dialog.Root;
export const SheetTrigger = Dialog.Trigger;
export const SheetClose = Dialog.Close;

const SheetOverlay = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof Dialog.Overlay>
>(({ className, ...props }, ref) => (
  <Dialog.Overlay
    ref={ref}
    className={cn(
      'fixed inset-0 z-50 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0',
      className,
    )}
    {...props}
  />
));
SheetOverlay.displayName = 'SheetOverlay';

export const SheetContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof Dialog.Content>
>(({ className, children, ...props }, ref) => (
  <Dialog.Portal>
    <SheetOverlay />
    <Dialog.Content
      ref={ref}
      className={cn(
        'fixed right-0 top-0 z-50 flex h-full w-full max-w-[560px] flex-col gap-0 border-l border-border bg-surface shadow-xl',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=open]:slide-in-from-right-12 data-[state=closed]:slide-out-to-right-12',
        'duration-300',
        className,
      )}
      {...props}
    >
      {children}
      <Dialog.Close className="absolute right-5 top-5 rounded-md text-fg-muted transition-colors hover:bg-surface-elevated hover:text-fg p-1.5">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal>
));
SheetContent.displayName = 'SheetContent';

export const SheetHeader = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col gap-1.5 border-b border-border p-6', className)} {...props} />
);

export const SheetTitle = forwardRef<
  HTMLHeadingElement,
  ComponentPropsWithoutRef<typeof Dialog.Title>
>(({ className, ...props }, ref) => (
  <Dialog.Title
    ref={ref}
    className={cn('text-lg font-semibold tracking-tight text-fg', className)}
    {...props}
  />
));
SheetTitle.displayName = 'SheetTitle';

export const SheetDescription = forwardRef<
  HTMLParagraphElement,
  ComponentPropsWithoutRef<typeof Dialog.Description>
>(({ className, ...props }, ref) => (
  <Dialog.Description
    ref={ref}
    className={cn('text-sm text-fg-muted', className)}
    {...props}
  />
));
SheetDescription.displayName = 'SheetDescription';
```

- [ ] **Step 4:** Add `src/shared/ui/scroll-area.tsx`, `avatar.tsx`, `badge.tsx`, `separator.tsx`, `tooltip.tsx`, `skeleton.tsx`, `sonner.tsx`. Each is a thin Radix wrapper + Tailwind. Follow the same pattern as above. Specifically:
  - `badge.tsx`: cva-driven variants `default`, `outline`, `success`, `warning`, `pop`. Used by `<CitationBadge>` and run status pills.
  - `sonner.tsx`: wraps Sonner's `<Toaster />` with our color tokens (`theme="system"` reading `document.documentElement.classList`).
  - `skeleton.tsx`: `<div className="animate-pulse rounded-md bg-surface-elevated" />`.
  - `avatar.tsx`: thin Radix Avatar wrapper.
  - `scroll-area.tsx`: thin Radix ScrollArea wrapper.
  - `separator.tsx`: Radix Separator.
  - `tooltip.tsx`: Radix Tooltip composition. Default delay 200ms.

The standard shadcn-canary implementations for these (MIT) work as-is with our tokens — copy and replace `bg-background`/`text-foreground` with our `bg-bg`/`text-fg` etc.

- [ ] **Step 5:** Barrel export at `src/shared/ui/index.ts`:

```typescript
export { Button } from './button';
export { Card, CardHeader, CardTitle, CardDescription, CardContent } from './card';
export {
  Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetClose,
} from './sheet';
export { ScrollArea } from './scroll-area';
export { Avatar, AvatarImage, AvatarFallback } from './avatar';
export { Badge } from './badge';
export { Separator } from './separator';
export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './tooltip';
export { Skeleton } from './skeleton';
export { Toaster } from './sonner';
```

- [ ] **Step 6:** Configure path alias in `tsconfig.app.json` (or whichever is the project file) for `@/`:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  }
}
```

And matching alias in `vite.config.ts`:

```typescript
import path from 'node:path';
// inside defineConfig({ ... }):
resolve: { alias: { '@': path.resolve(__dirname, 'src') } }
```

- [ ] **Step 7:** Verify build is clean:

```
pnpm typecheck && pnpm lint && pnpm build
```

- [ ] **Step 8:** Commit.

```
git add apps/web/src/shared/ui/ apps/web/tsconfig.app.json apps/web/vite.config.ts
git commit -m "feat(web): shadcn-style UI primitives on Radix"
```

---

## Task 3 — App shell: Sidebar + Main + FeedPanel

**Files:** `apps/web/src/shared/layout/AppShell.tsx`, `Sidebar.tsx`, `FeedPanel.tsx`; remove old `shared/components/AppShell.tsx`; update `router.tsx`.

The shell is the Image #7 layout: dark sidebar with brand at top + icon nav + user/theme at bottom, light/dark main canvas, persistent right feed panel.

- [ ] **Step 1:** `src/shared/layout/Sidebar.tsx`:

```tsx
import { NavLink } from 'react-router-dom';
import { MessageSquareText, BotMessageSquare, Plug, Database, Settings } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '@/shared/utils/cn';
import { useThemeStore } from '@/shared/theme';
import { Button } from '@/shared/ui';

const navItems = [
  { to: '/chat', label: 'Chat', icon: MessageSquareText },
  { to: '/agents', label: 'Agents', icon: BotMessageSquare },
  { to: '/connectors', label: 'Connectors', icon: Plug },
  { to: '/records', label: 'Records', icon: Database },
];

export function Sidebar() {
  const theme = useThemeStore(s => s.theme);
  const toggle = useThemeStore(s => s.toggle);

  return (
    <aside className="flex h-screen w-[248px] flex-col bg-sidebar-bg text-sidebar-fg p-4 gap-2">
      <div className="flex items-center gap-2 px-2 py-3">
        <div className="grid h-9 w-9 place-items-center rounded-md bg-primary text-primary-fg font-bold">M</div>
        <div>
          <div className="text-base font-semibold tracking-tight">Munim</div>
          <div className="text-xs text-sidebar-muted">AI for D2C</div>
        </div>
      </div>

      <nav className="flex flex-col gap-1 mt-2">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors',
                isActive
                  ? 'bg-sidebar-hover text-sidebar-fg'
                  : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="sidebar-active"
                    className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-primary"
                  />
                )}
                <item.icon className="h-4 w-4" />
                <span>{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggle}
          className="text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg justify-start"
        >
          <Settings className="h-4 w-4" />
          Theme: {theme}
        </Button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2:** `src/shared/layout/FeedPanel.tsx`:

```tsx
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
```

- [ ] **Step 3:** `src/shared/layout/AppShell.tsx`:

```tsx
import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { FeedPanel } from './FeedPanel';
import { fadeUp } from '@/shared/utils/motion';

export function AppShell() {
  const location = useLocation();
  return (
    <div className="grid h-screen grid-cols-[248px_minmax(0,1fr)_360px] bg-bg">
      <Sidebar />
      <main className="overflow-y-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
            className="min-h-full"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      <FeedPanel />
    </div>
  );
}
```

- [ ] **Step 4:** Update `src/router.tsx` — `/` redirects to `/chat`, mounts `<AppShell />` as the layout wrapper, routes for `/chat`, `/agents`, `/connectors`, `/records`. Keep `<NotFoundPage />` outside the shell or inside (your call — inside is cleaner). Delete obsolete `src/pages/IndexPage.tsx` if it's redundant with the new shell+home.

- [ ] **Step 5:** Mount Sonner in `src/main.tsx`:

```tsx
import { Toaster } from '@/shared/ui';
// inside the render tree, after <App />:
<Toaster position="bottom-right" />
```

- [ ] **Step 6:** Migrate any imports of the old `shared/components/{AppShell,Button,Card}` to `shared/layout` / `shared/ui`. Run `pnpm typecheck` until green. Then delete the legacy files.

- [ ] **Step 7:** Build + manual smoke (open `pnpm dev`, eyeball the shell):

```
pnpm typecheck && pnpm lint && pnpm build
pnpm dev  # open http://localhost:5173, verify shell renders in both light + dark
```

The right panel renders a "Loading…" or empty state at this point — the feed module isn't built yet. That's fine.

- [ ] **Step 8:** Commit.

```
git add apps/web/src/shared/layout/ apps/web/src/router.tsx apps/web/src/main.tsx
git rm apps/web/src/shared/components/AppShell.tsx apps/web/src/shared/components/Button.tsx apps/web/src/shared/components/Card.tsx
git commit -m "feat(web): app shell with sidebar + feed panel layout"
```

---

## Task 4 — Feed module (agent nudges)

**Files:** `src/modules/feed/api/client.ts` (re-export from agent_runs), `src/modules/feed/hooks/useAgentNudges.ts`, `src/modules/feed/components/NudgeFeed.tsx`, `NudgeCard.tsx`.

Pulls from `GET /agent-runs?limit=10`, surfaces the last 10 agent decisions (across runs) as nudges. Polls every 30s. On new arrivals (run_log_id > last seen), fires a Sonner toast with a "Review" action that opens the corresponding run detail sheet on the Agents page.

- [ ] **Step 1:** `src/modules/feed/hooks/useAgentNudges.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { fetchAgentRuns, type AgentRunSummary } from '@/modules/agent_runs/api/client';

const POLL_MS = 30_000;

export function useAgentNudges() {
  const navigate = useNavigate();
  const lastSeenId = useRef<number | null>(null);

  const query = useQuery({
    queryKey: ['agent-runs', { limit: 10 }],
    queryFn: () => fetchAgentRuns({ limit: 10 }),
    refetchInterval: POLL_MS,
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    const items = query.data?.items;
    if (!items?.length) return;
    const newest = items[0];
    if (lastSeenId.current !== null && newest.run_log_id > lastSeenId.current) {
      toast(`Agent proposed ${newest.actions_proposed} action${newest.actions_proposed === 1 ? '' : 's'}`, {
        description: `${newest.orders_scanned} orders scanned by ${newest.agent}.`,
        action: {
          label: 'Review',
          onClick: () => navigate(`/agents?run=${newest.run_log_id}`),
        },
      });
    }
    lastSeenId.current = newest.run_log_id;
  }, [query.data, navigate]);

  return query;
}

export type { AgentRunSummary };
```

- [ ] **Step 2:** `src/modules/feed/components/NudgeCard.tsx`:

```tsx
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { Card } from '@/shared/ui';
import { Button } from '@/shared/ui';
import type { AgentRunSummary } from '@/modules/feed/hooks/useAgentNudges';
import { fadeUp } from '@/shared/utils/motion';

interface Props {
  nudge: AgentRunSummary;
}

export function NudgeCard({ nudge }: Props) {
  const navigate = useNavigate();
  const isAction = nudge.actions_proposed > 0;
  return (
    <motion.div variants={fadeUp}>
      <Card className="p-4 flex flex-col gap-3 bg-surface">
        <div className="flex items-start gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-accent text-accent-fg">
            <Sparkles className="h-4 w-4" />
          </div>
          <div className="flex flex-col gap-0.5 min-w-0">
            <div className="text-sm font-medium text-fg truncate">
              {isAction
                ? `${nudge.actions_proposed} action${nudge.actions_proposed === 1 ? '' : 's'} proposed`
                : 'No actions proposed'}
            </div>
            <div className="text-xs text-fg-muted">
              {nudge.orders_scanned} orders scanned · {new Date(nudge.finished_at).toLocaleString()}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={isAction ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => navigate(`/agents?run=${nudge.run_log_id}`)}
            className="flex-1"
          >
            {isAction ? 'Review proposals' : 'View run'}
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}
```

- [ ] **Step 3:** `src/modules/feed/components/NudgeFeed.tsx`:

```tsx
import { motion } from 'framer-motion';
import { useAgentNudges } from '@/modules/feed/hooks/useAgentNudges';
import { NudgeCard } from './NudgeCard';
import { Skeleton } from '@/shared/ui';
import { stagger } from '@/shared/utils/motion';

export function NudgeFeed() {
  const { data, isLoading, error } = useAgentNudges();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-[88px] w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-sm text-destructive">Couldn't load nudges. Server unreachable.</div>
    );
  }

  if (!data?.items.length) {
    return (
      <div className="text-sm text-fg-muted">
        No agent runs yet. Trigger one from the Agents page.
      </div>
    );
  }

  return (
    <motion.div variants={stagger} initial="hidden" animate="visible" className="flex flex-col gap-3">
      {data.items.map(nudge => (
        <NudgeCard key={nudge.run_log_id} nudge={nudge} />
      ))}
    </motion.div>
  );
}
```

- [ ] **Step 4:** Build + smoke. The feed should render in the right panel. With the existing 1 agent run from the live smoke, you should see 1 nudge card.

- [ ] **Step 5:** Commit.

```
git add apps/web/src/modules/feed/
git commit -m "feat(web): agent nudge feed with polling + sonner toast on new arrivals"
```

---

## Task 5 — Agent Runs module

**Files:** `src/modules/agent_runs/{api,types,hooks,components}/`, `AgentRunsPage.tsx`.

The page has a header (title + manual-trigger button), a table of runs, and a side sheet showing run detail with a donut chart of action distribution + per-order decisions.

- [ ] **Step 1:** `src/modules/agent_runs/api/client.ts` — typed Zod-validated fetchers:

```typescript
import { z } from 'zod';
import { api } from '@/shared/api/client';

const AgentRunSummary = z.object({
  run_log_id: z.number(),
  run_id: z.string(),
  agent: z.string(),
  orders_scanned: z.number(),
  actions_proposed: z.number(),
  started_at: z.string(),
  finished_at: z.string(),
});

const AgentRunDecision = z.object({
  record_id: z.number(),
  source_id: z.string(),
  score: z.number(),
  action: z.enum(['convert_to_prepaid', 'confirmation_call', 'no_action']),
  estimated_inr_saved: z.string(),
  signal_scores: z.record(z.string(), z.number()),
  signal_diagnostics: z.record(z.string(), z.record(z.string(), z.unknown())),
  weights: z.record(z.string(), z.number()),
  reasoning: z.string(),
});

const AgentRunDetail = AgentRunSummary.extend({
  decisions: z.array(AgentRunDecision),
});

const ListResponse = z.object({ items: z.array(AgentRunSummary) });

export type AgentRunSummary = z.infer<typeof AgentRunSummary>;
export type AgentRunDecision = z.infer<typeof AgentRunDecision>;
export type AgentRunDetail = z.infer<typeof AgentRunDetail>;

export async function fetchAgentRuns(params: { limit?: number } = {}) {
  return api
    .get('agent-runs', { searchParams: { limit: params.limit ?? 50 } })
    .json<{ success: true; data: unknown }>()
    .then(r => ListResponse.parse(r.data));
}

export async function fetchAgentRun(runLogId: number) {
  return api
    .get(`agent-runs/${runLogId}`)
    .json<{ success: true; data: unknown }>()
    .then(r => AgentRunDetail.parse(r.data));
}

export async function triggerAgent(name: string) {
  return api
    .post(`agents/${name}/run`)
    .json<{ success: true; data: { run: unknown } }>()
    .then(r => AgentRunSummary.parse((r.data as { run: unknown }).run));
}
```

- [ ] **Step 2:** Hooks — `useAgentRuns.ts` (TanStack Query list, key `['agent-runs', { limit }]`, refetch on focus), `useTriggerAgent.ts` (mutation, on success: invalidate `['agent-runs']`, toast a success message with the new run_log_id).

- [ ] **Step 3:** `components/ActionDonut.tsx`:

```tsx
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import type { AgentRunDecision } from '@/modules/agent_runs/api/client';

const COLORS = {
  convert_to_prepaid: 'hsl(263 70% 60%)',
  confirmation_call: 'hsl(38 92% 50%)',
  no_action: 'hsl(263 10% 60%)',
};

const LABELS = {
  convert_to_prepaid: 'Convert to prepaid',
  confirmation_call: 'Confirmation call',
  no_action: 'No action',
};

export function ActionDonut({ decisions }: { decisions: AgentRunDecision[] }) {
  const counts = decisions.reduce<Record<string, number>>((acc, d) => {
    acc[d.action] = (acc[d.action] ?? 0) + 1;
    return acc;
  }, {});
  const data = Object.entries(counts).map(([action, count]) => ({
    name: LABELS[action as keyof typeof LABELS],
    value: count,
    action,
  }));

  if (data.length === 0) return null;

  return (
    <div className="h-[200px] w-full">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" innerRadius={56} outerRadius={84} paddingAngle={2}>
            {data.map(entry => (
              <Cell key={entry.action} fill={COLORS[entry.action as keyof typeof COLORS]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: 'hsl(var(--surface))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 12,
              fontSize: 13,
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4:** `components/RunsTable.tsx` — a Card-wrapped semantic table with columns (Run, Agent, Scanned, Proposed, Started, Status). Rows are clickable and open the detail sheet via URL param `?run=<id>`. Empty state with a "Trigger an agent" CTA.

- [ ] **Step 5:** `components/RunDetailSheet.tsx` — controlled by `?run=<id>` query param. On mount, fetch detail; show:
  - Header: agent name + run_id + started/finished
  - Donut of action distribution
  - List of decisions: each with action badge (color-coded), order source_id, score (e.g. "0.62"), estimated INR saved (₹), signal scores as small pills, expandable diagnostics, full reasoning string.

Use the `Sheet` UI primitive. Animations come from Radix data-state + the sheet's slide-in.

- [ ] **Step 6:** `components/TriggerAgentButton.tsx` — primary button in the page header that calls `useTriggerAgent('rto_mitigator')`. Disabled while pending; shows a spinner; on success toasts "Agent ran. N orders scanned, M actions proposed."

- [ ] **Step 7:** `AgentRunsPage.tsx` — composes header + table + sheet, reads `?run=` URL param.

- [ ] **Step 8:** Build + smoke. Open `/agents`, see the existing 1 run; click it, sheet slides in with the convert_to_prepaid decision + donut. Click "Run agent now" — toast appears, table updates, feed panel updates (this exercises the polling integration end to end).

- [ ] **Step 9:** Commit.

```
git add apps/web/src/modules/agent_runs/
git commit -m "feat(web): agent runs page with detail sheet + action donut + manual trigger"
```

---

## Task 6 — Chat module

**Files:** `src/modules/chat/{api,types,hooks,components}/`, `ChatPage.tsx`.

Chat is the headline-scored axis. Behavior:
- One-shot (no streaming, no history). User types → POST `/chat/messages` → response renders with citation badges.
- Each citation badge `[cite:N]` in the response renders inline as a clickable pill. Hovering shows the cited record's source_id + entity_type via Tooltip; clicking can navigate to `/records?id=<record_id>` (light touch — only if records page supports the param, otherwise omit).
- Avatar persona at top-left (matches Image #8): soft chat-bubble framing, gentle entrance animation on each new message.
- Typing indicator dots while the response is pending.

- [ ] **Step 1:** `api/client.ts`:

```typescript
import { z } from 'zod';
import { api } from '@/shared/api/client';

const RowCitation = z.object({
  id: z.number(),
  source_id: z.string(),
  source_system: z.string(),
  entity_type: z.string(),
});

const ChatResponse = z.object({
  text: z.string(),
  used_citations: z.array(z.number()),
  available_citations: z.array(RowCitation),
});

export type RowCitation = z.infer<typeof RowCitation>;
export type ChatResponse = z.infer<typeof ChatResponse>;

export async function sendChatMessage(prompt: string) {
  return api
    .post('chat/messages', { json: { prompt } })
    .json<{ success: true; data: unknown }>()
    .then(r => ChatResponse.parse(r.data));
}
```

- [ ] **Step 2:** Types — `Message` (id, role: 'user'|'assistant', text, citations, timestamp). Local to the module.

- [ ] **Step 3:** `hooks/useChat.ts`:

```typescript
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { sendChatMessage, type RowCitation } from '@/modules/chat/api/client';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  citations?: RowCitation[];
  timestamp: number;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const mutation = useMutation({
    mutationFn: sendChatMessage,
    onSuccess: data => {
      setMessages(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: data.text,
          citations: data.available_citations,
          timestamp: Date.now(),
        },
      ]);
    },
  });

  function send(prompt: string) {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setMessages(prev => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', text: trimmed, timestamp: Date.now() },
    ]);
    mutation.mutate(trimmed);
  }

  return { messages, send, isPending: mutation.isPending, error: mutation.error };
}
```

- [ ] **Step 4:** `components/CitationBadge.tsx`:

```tsx
import { motion } from 'framer-motion';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui';
import { pulse } from '@/shared/utils/motion';
import type { RowCitation } from '@/modules/chat/api/client';

interface Props {
  citation: RowCitation;
}

export function CitationBadge({ citation }: Props) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.button
          {...pulse}
          className="inline-flex items-center align-baseline mx-0.5 px-1.5 py-0.5 rounded-md text-[11px] font-medium bg-accent text-accent-fg hover:opacity-90 transition-opacity"
        >
          {citation.id}
        </motion.button>
      </TooltipTrigger>
      <TooltipContent>
        <div className="text-xs">
          <div className="font-medium">{citation.entity_type}</div>
          <div className="text-fg-muted">{citation.source_system} · {citation.source_id}</div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
```

- [ ] **Step 5:** `components/MessageBubble.tsx`:

A renderer that takes a `ChatMessage` and (for assistant messages) parses the `text` with a regex (`/\[cite:([\d,\s]+)\]/g`) splitting the text into segments and citation groups. Each citation group renders a row of `<CitationBadge>` for each id referenced (looked up in `message.citations`). User messages render a plain right-aligned bubble in primary color; assistant messages render left-aligned with the avatar leading.

Provide the full parser:

```tsx
import { motion } from 'framer-motion';
import { Avatar, AvatarFallback } from '@/shared/ui';
import { CitationBadge } from './CitationBadge';
import { fadeUp } from '@/shared/utils/motion';
import type { ChatMessage } from '@/modules/chat/hooks/useChat';

const CITE_RE = /\[cite:([\d,\s]+)\]/g;

function renderText(text: string, citations: ChatMessage['citations']) {
  const parts: (string | { ids: number[] })[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = CITE_RE.exec(text)) !== null) {
    if (m.index > lastIndex) parts.push(text.slice(lastIndex, m.index));
    parts.push({ ids: m[1].split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n)) });
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));

  return parts.map((part, i) => {
    if (typeof part === 'string') return <span key={i}>{part}</span>;
    return (
      <span key={i} className="inline-flex items-baseline">
        {part.ids.map(id => {
          const c = citations?.find(x => x.id === id);
          return c ? <CitationBadge key={id} citation={c} /> : null;
        })}
      </span>
    );
  });
}

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className={isUser ? 'flex justify-end' : 'flex items-start gap-3'}
    >
      {!isUser && (
        <Avatar className="h-9 w-9 shrink-0 bg-accent text-accent-fg grid place-items-center font-semibold">
          <AvatarFallback>M</AvatarFallback>
        </Avatar>
      )}
      <div
        className={
          isUser
            ? 'max-w-[75%] rounded-2xl rounded-br-sm bg-primary text-primary-fg px-4 py-2.5 text-sm'
            : 'max-w-[75%] rounded-2xl rounded-tl-sm bg-surface-elevated border border-border px-4 py-2.5 text-sm leading-relaxed text-fg'
        }
      >
        {isUser ? message.text : renderText(message.text, message.citations)}
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 6:** `components/MessageList.tsx` — scrollable container with auto-scroll to bottom on new messages. Show a typing indicator (three dots, bouncing) while `isPending`. Empty state: a friendly "Ask about your sales, orders, RTO risk…" prompt with 3-4 suggestion chips that trigger `send()` on click.

- [ ] **Step 7:** `components/ChatInput.tsx` — textarea with auto-grow (max ~5 rows), Cmd/Ctrl+Enter to send (or just Enter), disabled while pending, primary send button with paper-plane icon.

- [ ] **Step 8:** `ChatPage.tsx` — composes header + message list + input.

- [ ] **Step 9:** Build + smoke. Type "How many orders are paid online?" and verify the response renders with the cite pill inline. Hover the badge — tooltip shows source_id. Try a question with no data ("What's the weather?") — assistant should respond gracefully (backend behavior).

- [ ] **Step 10:** Commit.

```
git add apps/web/src/modules/chat/
git commit -m "feat(web): chat page with citation badges + avatar persona"
```

---

## Task 7 — Polish + Connectors/Records light migration

**Files:** existing `modules/connectors/**`, `modules/records/**`, `modules/health/**`.

- [ ] **Step 1:** Audit imports of the old `shared/components/{Button,Card,EmptyState,Loader,NavLink,StatusBadge}`. Replace with `shared/ui` equivalents where 1:1 (Button, Card). For `EmptyState`/`Loader`/`StatusBadge`, leave alone if the visual gap is small; rewrite if it sticks out (subagent judgment).
- [ ] **Step 2:** Wrap each page's content in the same motion `fadeUp` wrapper used by AppShell for consistency.
- [ ] **Step 3:** Quick dark-mode QA pass: every page should look intentional in both themes. No hardcoded colors anywhere — all token-driven.
- [ ] **Step 4:** Commit.

```
git add apps/web/src/modules/connectors/ apps/web/src/modules/records/ apps/web/src/modules/health/
git commit -m "feat(web): connectors + records adopt new UI primitives + dark-mode polish"
```

---

## Task 8 — Live smoke + docs + final commit

- [ ] **Step 1:** Start backend + frontend:

```
# Terminal 1
cd apps/api; $env:Path = "C:\Users\loots\.local\bin;$env:Path"; uv run uvicorn munim.main:app --reload
# Terminal 2
cd apps/web; pnpm dev
```

- [ ] **Step 2:** Walk the smoke recipe (eyeball + screenshot each step):
  1. `/chat` opens. Type "How many orders are paid online?" → assistant responds with `[cite:N]` rendered as pills, hover tooltip shows source_id.
  2. `/agents` shows the run table. Click "Run agent now" → toast appears, table updates with new row, feed panel updates.
  3. Click a row → sheet slides in with donut + decisions. Hover the convert action → see signal scores + reasoning. Close sheet.
  4. Toggle theme via sidebar → entire app switches cleanly, no hardcoded colors leaking.
  5. `/connectors` and `/records` look intentional in both themes.
  6. Resize to ~1280px — feed panel still visible. Below 1024px feed panel hides (acceptable).

- [ ] **Step 3:** `CHANGELOG.md` entry at top — what shipped, files touched, deps added, screenshots taken (committed to `docs/screenshots/phase-7/` if you took them).
- [ ] **Step 4:** `context.md` — bump Now to "Phase 7 complete," append to Done, push Next forward.
- [ ] **Step 5:** Commit:

```
git add CHANGELOG.md context.md docs/screenshots/
git commit -m "docs(phase-7): record frontend shipping + screenshots"
```

---

## Self-review

**Spec coverage:**
- App shell with persistent agent-nudge feed: Tasks 3 + 4. ✓
- Chat page with citation badges: Task 6. ✓
- Agent Runs page with detail + donut + manual trigger: Task 5. ✓
- Lavender palette + light/dark: Task 1. ✓
- Motion: Task 1 (variants) + applied throughout. ✓
- Connectors/Records inherit shell: Task 7. ✓

**Vibe coverage:**
- Image #7 layout (sidebar + main + right feed): Task 3. ✓
- Image #8 chat-with-persona avatar: Task 6 (MessageBubble + ChatAvatar). ✓
- Image #8 soft pop accents: `pop` color reserved for agent nudges and emphasis CTAs.
- "Smooth animations": `fadeUp`/`stagger`/`slideInRight`/`pulse` used consistently; never gratuitous.

**Type/name consistency:**
- `AgentRunSummary` Zod schema shape matches the backend's `AgentRunSummary` Pydantic schema (Phase 6).
- `RowCitation` matches the backend's `RowCitation` (Phase 5).
- `AgentActionType` values match the backend's StrEnum.

**Test discipline:**
- Frontend tests are NOT exhaustive in this phase. The Zod schemas at the boundary catch shape drift at runtime. Component tests are deferred — manual smoke is the gate, per the brief's 48-hour reality.
- If the implementer has time, add Vitest tests for the citation parser (regex + lookup) and the agent-run polling effect (new-arrival detection). Otherwise skip.

**Honest gaps documented:**
- No streaming chat. Typing indicator covers the latency.
- No chat history persistence. Stateless per Phase 5 decision.
- No mobile layout. Desktop-first.
- Component tests minimal. Zod boundary validation + manual smoke is the v0 gate.
- Polling at 30s for nudges; an SSE upgrade would be one library swap.

**Risk callouts for the reviewer:**
- shadcn-style components were adapted manually (not `pnpm dlx shadcn init`) because we're on Tailwind v4. Watch for animation classes (`data-[state=open]:animate-in` etc.) — Tailwind v4 supports them via the `tw-animate-css` plugin OR vanilla CSS keyframes. If the build complains, add `tw-animate-css` to `globals.css` (`@import 'tw-animate-css';`).
- The `useAgentNudges` toast fires on EVERY new run_log_id during polling, including ones the user triggered themselves. Acceptable for v0; if it becomes annoying, dedupe against the mutation result in `useTriggerAgent`.
- `@/` path alias must be set up in BOTH `tsconfig.app.json` AND `vite.config.ts` — easy to forget one.
