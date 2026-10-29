import { Headset } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { StepProps } from '../JourneyPage'

export default function Handoff({ journey }: StepProps) {
  const { t } = useTranslation()
  const failed = journey.kyc_result?.checks.filter((c) => c.status === 'fail') ?? []
  return (
    <div className="flex flex-col items-center gap-4 px-6 py-10 text-center">
      <Headset size={48} className="text-brand" aria-hidden />
      <h1 className="text-2xl font-bold">{t('handoffTitle')}</h1>
      <p className="text-muted">{t('handoffBody')}</p>
      {journey.handoff?.note && <p className="card w-full p-4 text-left text-sm">{journey.handoff.note}</p>}
      {failed.length > 0 && (
        <ul className="card w-full list-disc p-4 pl-8 text-left text-sm text-bad">
          {failed.map((c) => (
            <li key={c.id}>{c.message}</li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">Reference: {journey.journey_id}</p>
    </div>
  )
}
