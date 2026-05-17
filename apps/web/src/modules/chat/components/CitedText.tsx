import { Fragment, type ReactElement, type ReactNode } from 'react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui';
import { CitationBadge } from './CitationBadge';
import type { RowCitation } from '@/modules/chat/api/client';

const UNVERIFIED_SENTINEL = '[unverified number removed]';

function UnverifiedPlaceholder() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex items-baseline text-fg-subtle italic cursor-help underline decoration-dotted decoration-fg-subtle/60 underline-offset-2">
          a number
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <div className="text-xs text-fg-muted leading-relaxed">
          I had a number here but couldn't trace it back to a specific row, so I
          dropped it rather than show something unverified. Try asking the question
          again — the model often picks up the citation on a retry.
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

// Matches `<claim>[cite:N,M,...]` where <claim> is either a number with optional
// currency prefix and optional trailing unit/word (e.g. "Rs.6796.00", "4 orders",
// "12%", "₹2,500"), OR any single word as a fallback. The regex captures the
// claim text in group 1 and the comma-separated id list in group 2.
const CITED_CLAIM_RE =
  /((?:₹|Rs\.?\s*|\$)?\d[\d,.]*(?:\s*%|\s+[\w%]+)?|\b\w+)\s*\[cite:([\d,\s]+)\]/g;
const BARE_CITE_RE = /\[cite:[\d,\s]+\]/g;

interface CitedTextProps {
  text: string;
  citations: RowCitation[] | undefined;
}

export function CitedText({ text, citations }: CitedTextProps): ReactElement {
  const byId = new Map<number, RowCitation>(citations?.map((c) => [c.record_id, c]) ?? []);
  const out: ReactNode[] = [];
  let cursor = 0;
  CITED_CLAIM_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CITED_CLAIM_RE.exec(text)) !== null) {
    const start = match.index;
    const claim = match[1];
    if (start > cursor) {
      out.push(text.slice(cursor, start));
    }
    const ids = match[2]
      .split(',')
      .map((s) => Number.parseInt(s.trim(), 10))
      .filter((n) => Number.isFinite(n));
    const resolved = ids
      .map((id) => byId.get(id))
      .filter((c): c is RowCitation => c !== undefined);
    if (resolved.length > 0) {
      out.push(<CitationBadge citations={resolved}>{claim}</CitationBadge>);
    } else {
      out.push(claim);
    }
    cursor = start + match[0].length;
  }
  let trailing = text.slice(cursor);
  trailing = trailing.replace(BARE_CITE_RE, '');
  if (trailing.length > 0) out.push(trailing);

  const expanded = out.flatMap((piece, i) => {
    if (typeof piece !== 'string') return [<Fragment key={`f${i}`}>{piece}</Fragment>];
    if (!piece.includes(UNVERIFIED_SENTINEL)) {
      return [<Fragment key={`s${i}`}>{piece}</Fragment>];
    }
    const chunks = piece.split(UNVERIFIED_SENTINEL);
    const result: ReactNode[] = [];
    chunks.forEach((chunk, idx) => {
      if (chunk.length > 0) {
        result.push(<Fragment key={`s${i}-${idx}t`}>{chunk}</Fragment>);
      }
      if (idx < chunks.length - 1) {
        result.push(<UnverifiedPlaceholder key={`s${i}-${idx}u`} />);
      }
    });
    return result;
  });

  return <>{expanded}</>;
}
