import { useTranslation } from 'react-i18next'

const ORDER = ['chat', 'quote', 'consent', 'kyc', 'esign']

export function Stepper({ kind }: { kind: string }) {
  const { t } = useTranslation()
  const steps = [
    { keys: ['chat'], label: t('stepAdvisor') },
    { keys: ['quote'], label: t('stepQuote') },
    { keys: ['consent', 'kyc'], label: t('stepKyc') },
    { keys: ['esign'], label: t('stepSign') },
    { keys: ['track'], label: t('stepTrack') },
  ]
  const at = ORDER.indexOf(kind)
  return (
    <ol className="flex gap-1 px-4 pt-3" aria-label="Progress">
      {steps.map((s, i) => {
        const idx = Math.min(...s.keys.map((k) => (ORDER.indexOf(k) === -1 ? 99 : ORDER.indexOf(k))))
        const active = s.keys.includes(kind)
        const done = at > -1 && idx < at && !active
        return (
          <li key={i} className="flex flex-1 flex-col gap-1">
            <span className={`h-1.5 rounded-full ${done || active ? 'bg-brand' : 'bg-line'}`} />
            <span className={`text-[11px] ${active ? 'font-semibold text-brand' : 'text-muted'}`}>{s.label}</span>
          </li>
        )
      })}
    </ol>
  )
}
