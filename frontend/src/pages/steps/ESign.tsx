import { CheckCircle2, PenLine } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { inr } from '../../i18n'
import type { StepProps } from '../JourneyPage'

export default function ESign({ journey, resume, busy }: StepProps) {
  const { t } = useTranslation()
  const p = journey.pending
  const [otp, setOtp] = useState('')
  const slots = useMemo(() => {
    const out: string[] = []
    const d = new Date()
    for (let i = 1; out.length < 6; i++) {
      const day = new Date(d.getTime() + i * 86400000)
      if (day.getDay() === 0) continue
      const label = day.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
      out.push(`${label}, 10am-1pm`, `${label}, 2pm-6pm`)
    }
    return out.slice(0, 6)
  }, [])
  const [slot, setSlot] = useState(slots[0])
  if (p?.kind !== 'esign') return null
  const q = p.quote

  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      <div className="rounded-xl bg-ok-soft px-3 py-2 text-sm text-ok">
        <CheckCircle2 size={16} className="mr-1 inline" /> Business verified{p.business ? `: ${p.business}` : ''}
      </div>
      <h1 className="text-xl font-bold">{t('esignTitle')}</h1>
      <section className="card flex flex-col gap-1 p-4 text-sm">
        {q.items
          .filter((i) => i.selected)
          .map((i) => (
            <div key={i.product_id} className="flex justify-between gap-2">
              <span>
                {i.name} {i.qty > 1 && `× ${i.qty}`}
              </span>
              <span>{inr(i.monthly)}</span>
            </div>
          ))}
        <div className="mt-2 flex justify-between border-t border-line pt-2 font-semibold">
          <span>{t('yourPlan')}</span>
          <span>
            {inr(q.monthly_with_gst)}
            {t('perMonth')} <span className="font-normal text-muted">({t('inclGst')})</span>
          </span>
        </div>
        <p className="text-muted">
          {q.contract_months} {t('months')} · {t('oneTimeSetup')}: {inr(q.setup_total)}
          {q.setup_emi ? ` (${inr(q.setup_emi_monthly)} × 6)` : ''}
        </p>
      </section>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">{t('installSlot')}</span>
        <select value={slot} onChange={(e) => setSlot(e.target.value)} className="rounded-lg border border-line bg-white px-3 py-2">
          {slots.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">OTP</span>
        <input
          inputMode="numeric"
          autoComplete="one-time-code"
          value={otp}
          onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
          className="rounded-lg border border-line px-3 py-2 text-center font-mono text-xl tracking-[0.5em]"
          placeholder="••••••"
        />
        <span className="text-muted">{t('otpHint')}</span>
        {p.error && <span className="text-bad">{p.error}</span>}
      </label>
      <button className="btn btn-primary w-full" disabled={busy || otp.length !== 6} onClick={() => resume({ kind: 'esign', otp, slot })}>
        <PenLine size={18} /> {t('confirmOrder')}
      </button>
    </div>
  )
}
