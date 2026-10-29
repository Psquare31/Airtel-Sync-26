import { Check, Lock, Minus, Pencil, Phone, Plus, Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { inr } from '../../i18n'
import type { Quote, QuoteItem } from '../../types'
import type { StepProps } from '../JourneyPage'

const PER_UNIT = new Set(['per line', 'per user', 'per device', 'per camera', 'per counter', 'per vehicle', 'per channel'])

export default function QuoteStep({ journey, resume, busy }: StepProps) {
  const { t } = useTranslation()
  const pending = journey.pending
  if (pending?.kind !== 'quote') return null
  const quote: Quote = pending.quote
  const why = journey.explanation?.why ?? {}
  const included = quote.items.filter((i) => i.selected)
  const optional = quote.items.filter((i) => !i.selected && !i.locked)
  const locked = quote.items.filter((i) => i.locked)

  const update = (patch: Record<string, unknown>) => resume({ kind: 'quote', action: 'update', ...patch })

  return (
    <div className="flex flex-col gap-4 px-4 py-4 pb-40">
      <section className="card flex flex-col gap-2 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-brand">
          <Sparkles size={16} aria-hidden /> {t('whyThis')}
        </p>
        <p className="leading-relaxed">{journey.explanation?.summary}</p>
        {journey.recommendation?.notes.map((n) => (
          <p key={n} className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
            {n}
          </p>
        ))}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold">{t('yourPlan')}</h2>
        {included.map((i) => (
          <Item key={i.product_id} item={i} why={why[i.product_id]} busy={busy} update={update} />
        ))}
      </section>

      {optional.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="font-semibold">{t('optional')}</h2>
          {optional.map((i) => (
            <Item key={i.product_id} item={i} why={why[i.product_id]} busy={busy} update={update} />
          ))}
        </section>
      )}

      {locked.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="font-semibold text-muted">{t('locked')}</h2>
          {locked.map((i) => (
            <div key={i.product_id} className="card flex items-start gap-3 p-3 opacity-70">
              <Lock size={18} className="mt-0.5 shrink-0 text-muted" aria-hidden />
              <div>
                <p className="font-medium">{i.name}</p>
                <p className="text-sm text-muted">{i.lock_reason}</p>
              </div>
            </div>
          ))}
        </section>
      )}

      <section className="card flex flex-col gap-3 p-4">
        <div className="flex items-center justify-between gap-3">
          <span className="font-medium">{t('contract')}</span>
          <div className="flex rounded-xl border border-line p-1" role="radiogroup" aria-label={t('contract')}>
            {quote.contract_options.map((m) => (
              <button
                key={m}
                role="radio"
                aria-checked={quote.contract_months === m}
                disabled={busy}
                onClick={() => update({ contract_months: m })}
                className={`rounded-lg px-3 py-1.5 text-sm ${quote.contract_months === m ? 'bg-brand text-white' : ''}`}
              >
                {m} {t('months')}
              </button>
            ))}
          </div>
        </div>
        {quote.setup_total > 0 && (
          <label className="flex items-center justify-between gap-3 text-sm">
            <span>
              {t('oneTimeSetup')}: <b>{inr(quote.setup_total)}</b>
              <br />
              <span className="text-muted">{t('spreadSetup')}</span>
            </span>
            <input
              type="checkbox"
              className="h-5 w-5 accent-[var(--color-brand)]"
              checked={quote.setup_emi}
              disabled={busy}
              onChange={(e) => update({ setup_emi: e.target.checked })}
            />
          </label>
        )}
        {quote.messages.map((m) => (
          <p key={m} className="text-sm text-muted">
            {m}
          </p>
        ))}
        <p className="text-sm text-muted">{t('activationIn', { days: quote.activation_days })}</p>
      </section>

      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-3xl flex-col gap-2 px-4 pb-[max(env(safe-area-inset-bottom),12px)] pt-3">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-3xl font-bold">
                {inr(quote.monthly_total)}
                <span className="text-base font-medium text-muted">{t('perMonth')}</span>
              </p>
              <p className="text-xs text-muted">
                {inr(quote.monthly_with_gst)} {t('inclGst')}
                {quote.setup_emi && quote.setup_emi_monthly > 0 && ` · + ${inr(quote.setup_emi_monthly)} setup × 6`}
              </p>
            </div>
            <div className="flex gap-1">
              <button className="btn btn-ghost px-2.5 py-2" onClick={() => resume({ kind: 'quote', action: 'edit_profile' })} disabled={busy} title={t('changeAnswers')} aria-label={t('changeAnswers')}>
                <Pencil size={18} />
              </button>
              <button className="btn btn-ghost px-2.5 py-2" onClick={() => resume({ kind: 'quote', action: 'talk_to_expert' })} disabled={busy} title={t('talkToExpert')} aria-label={t('talkToExpert')}>
                <Phone size={18} />
              </button>
            </div>
          </div>
          <button className="btn btn-primary w-full" disabled={busy} onClick={() => resume({ kind: 'quote', action: 'accept' })}>
            {t('continue')}
          </button>
        </div>
      </div>
    </div>
  )
}

function Item({ item, why, busy, update }: { item: QuoteItem; why?: string; busy: boolean; update: (p: Record<string, unknown>) => void }) {
  const { t } = useTranslation()
  const perUnit = PER_UNIT.has(item.unit)
  return (
    <div className={`card flex flex-col gap-2 p-3 ${item.selected ? '' : 'bg-white/60'}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium">
            {item.name}
            {item.qty > 1 && <span className="text-muted"> × {item.qty}</span>}
          </p>
          <p className="text-sm text-muted">{why || item.reason}</p>
        </div>
        <div className="text-right">
          <p className="font-semibold">{inr(item.monthly)}</p>
          {item.setup > 0 && <p className="text-xs text-muted">+{inr(item.setup)} setup</p>}
        </div>
      </div>
      <div className="flex items-center justify-between gap-2">
        {perUnit && item.selected ? (
          <div className="flex items-center gap-2 text-sm">
            <button className="rounded-lg border border-line p-1" disabled={busy || item.qty <= 1} onClick={() => update({ quantities: { [item.product_id]: item.qty - 1 } })} aria-label="Fewer">
              <Minus size={14} />
            </button>
            <span className="w-6 text-center">{item.qty}</span>
            <button className="rounded-lg border border-line p-1" disabled={busy} onClick={() => update({ quantities: { [item.product_id]: item.qty + 1 } })} aria-label="More">
              <Plus size={14} />
            </button>
            <span className="text-muted">{item.unit.replace('per ', '')}s</span>
          </div>
        ) : (
          <span className="text-xs text-muted">
            {inr(item.unit_price)} {item.unit} · {item.term_months} {t('months')}
          </span>
        )}
        {item.core ? (
          <span className="flex items-center gap-1 rounded-full bg-ok-soft px-2 py-0.5 text-xs text-ok">
            <Check size={12} /> {t('included')}
          </span>
        ) : (
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              className="peer sr-only"
              checked={item.selected}
              disabled={busy}
              onChange={(e) => update({ toggles: { [item.product_id]: e.target.checked } })}
              aria-label={item.name}
            />
            <span className="h-6 w-11 rounded-full bg-line transition peer-checked:bg-brand" />
            <span className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition peer-checked:translate-x-5" />
          </label>
        )}
      </div>
    </div>
  )
}
