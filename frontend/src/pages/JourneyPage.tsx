import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { Stepper } from '../components/Stepper'
import type { Journey } from '../types'
import Advisor from './steps/Advisor'
import Consent from './steps/Consent'
import ESign from './steps/ESign'
import Handoff from './steps/Handoff'
import Kyc from './steps/Kyc'
import QuoteStep from './steps/QuoteStep'

export interface StepProps {
  journey: Journey
  resume: (value: Record<string, unknown>) => Promise<Journey | undefined>
  busy: boolean
  setJourney: (j: Journey) => void
}

export default function JourneyPage() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const [journey, setJourney] = useState<Journey | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.journey(id).then(setJourney).catch(() => setErr(t('network')))
  }, [id, t])

  useEffect(() => {
    const onLang = (e: Event) => {
      api.setLang(id, (e as CustomEvent<string>).detail).then(setJourney).catch(() => {})
    }
    window.addEventListener('langchange', onLang)
    return () => window.removeEventListener('langchange', onLang)
  }, [id])

  useEffect(() => {
    if (journey?.lang && journey.lang !== i18n.language) i18n.changeLanguage(journey.lang)
    // only on first load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journey?.journey_id])

  const resume = useCallback(
    async (value: Record<string, unknown>) => {
      setBusy(true)
      setErr('')
      try {
        const j = await api.resume(id, value)
        setJourney(j)
        return j
      } catch (e) {
        setErr(e instanceof Error ? e.message : t('network'))
      } finally {
        setBusy(false)
      }
    },
    [id, t],
  )

  if (err && !journey) return <p className="p-6 text-bad">{err}</p>
  if (!journey) return <p className="p-6 text-muted">…</p>
  if (journey.order_id) return <Navigate to={`/track/${journey.order_id}`} replace />

  const kind = journey.pending?.kind
  const props: StepProps = { journey, resume, busy, setJourney }
  let body
  if (kind === 'quote') body = <QuoteStep {...props} />
  else if (kind === 'consent') body = <Consent {...props} />
  else if (kind === 'kyc') body = <Kyc {...props} />
  else if (kind === 'esign') body = <ESign {...props} />
  else if (kind === 'chat') body = <Advisor {...props} />
  else if (journey.handoff) body = <Handoff {...props} />
  else
    // not waiting and not handed off: an unexpected state, never pretend a person has taken over
    body = (
      <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
        <p className="text-bad">{t('network')}</p>
        <button className="btn btn-ghost" onClick={() => window.location.reload()}>
          Reload
        </button>
      </div>
    )

  return (
    <div className="flex flex-1 flex-col">
      <Stepper kind={kind ?? 'handoff'} />
      {journey.handoff && kind === 'chat' && (
        <div className="mx-4 mt-3 rounded-xl bg-warn-soft px-3 py-2 text-sm text-warn">{t('handoffBody')}</div>
      )}
      {err && <p className="mx-4 mt-3 rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad">{err}</p>}
      {body}
    </div>
  )
}
