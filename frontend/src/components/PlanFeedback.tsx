import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'

const REASONS = ['Too expensive', 'Missing something I need', "Has things I don't need", 'Wrong type of business']

/** Owner's verdict on the plan; a thumbs-down flags the conversation for the team to review. */
export function PlanFeedback({ journeyId }: { journeyId: string }) {
  const [state, setState] = useState<'ask' | 'why' | 'done'>('ask')
  const [reason, setReason] = useState<string | null>(null)
  const [comment, setComment] = useState('')

  async function send(rating: number, why?: string | null) {
    setState('done')
    try {
      await api.feedback(journeyId, rating, why ?? undefined, comment.trim() || undefined)
    } catch {
      /* feedback is best effort */
    }
  }

  if (state === 'done') return <p className="text-sm text-muted">Thanks, this helps the advisor get better.</p>
  return (
    <div className="flex flex-col gap-2 border-t border-line pt-3">
      {state === 'ask' ? (
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm">Is this plan right for your business?</span>
          <div className="flex gap-1">
            <button className="rounded-full border border-line p-2 hover:border-ok hover:text-ok" onClick={() => send(1)} aria-label="Yes, it fits">
              <ThumbsUp size={16} />
            </button>
            <button className="rounded-full border border-line p-2 hover:border-bad hover:text-bad" onClick={() => setState('why')} aria-label="No, it doesn't fit">
              <ThumbsDown size={16} />
            </button>
          </div>
        </div>
      ) : (
        <>
          <span className="text-sm">What's not right?</span>
          <div className="flex flex-wrap gap-2">
            {REASONS.map((r) => (
              <button key={r} className={`chip ${reason === r ? 'border-brand! bg-brand-soft text-brand' : ''}`} onClick={() => setReason(r)}>
                {r}
              </button>
            ))}
          </div>
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Anything else? (optional)"
            maxLength={300}
            className="rounded-lg border border-line px-3 py-2 text-sm"
          />
          <button className="btn btn-ghost self-start px-3 py-1.5 text-sm" disabled={!reason} onClick={() => send(-1, reason)}>
            Send feedback
          </button>
        </>
      )}
    </div>
  )
}
