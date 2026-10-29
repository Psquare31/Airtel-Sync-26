import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { StepProps } from '../JourneyPage'

export default function Consent({ journey, resume, busy }: StepProps) {
  const { t } = useTranslation()
  const p = journey.pending
  const [chosen, setChosen] = useState<Record<string, boolean>>({})
  if (p?.kind !== 'consent') return null
  const required = Object.entries(p.purposes).filter(([, v]) => v.required)
  const ok = required.every(([k]) => chosen[k])

  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      <div className="flex items-start gap-3">
        <ShieldCheck className="mt-1 shrink-0 text-ok" aria-hidden />
        <div>
          <h1 className="text-xl font-bold">{t('consentTitle')}</h1>
          <p className="text-muted">{t('consentBody')}</p>
        </div>
      </div>
      {Object.entries(p.purposes).map(([key, purpose]) => (
        <label key={key} className={`card flex cursor-pointer gap-3 p-4 ${chosen[key] ? 'border-brand' : ''}`}>
          <input
            type="checkbox"
            className="mt-1 h-5 w-5 shrink-0 accent-[var(--color-brand)]"
            checked={!!chosen[key]}
            onChange={(e) => setChosen((c) => ({ ...c, [key]: e.target.checked }))}
          />
          <span className="flex flex-col gap-1">
            <span className="font-semibold">
              {purpose.title}{' '}
              {purpose.required && <span className="rounded bg-brand-soft px-1.5 py-0.5 text-[11px] text-brand">{t('required')}</span>}
            </span>
            <span className="text-sm">{purpose.text}</span>
            <span className="text-xs text-muted">
              {t('retention')}: {purpose.retention}
            </span>
          </span>
        </label>
      ))}
      <details className="card p-4 text-sm">
        <summary className="cursor-pointer font-medium">{t('processors')}</summary>
        <ul className="mt-2 list-disc pl-5 text-muted">
          {p.processors.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
        <p className="mt-2 text-muted">{p.grievance}</p>
        <p className="mt-1 text-xs text-muted">Notice version {p.version} · DPDP Act, 2023</p>
      </details>
      <p className="text-xs text-muted">{t('withdraw')}</p>
      <button className="btn btn-primary w-full" disabled={!ok || busy} onClick={() => resume({ kind: 'consent', purposes: chosen })}>
        {t('agree')}
      </button>
    </div>
  )
}
