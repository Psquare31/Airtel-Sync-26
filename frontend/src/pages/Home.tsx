import { Bell, FileCheck2, MessageCircle, Receipt, Search } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { LANGS, setLanguage } from '../i18n'

export default function Home() {
  const { t, i18n } = useTranslation()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const partner = params.get('partner')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [orderId, setOrderId] = useState('')

  async function start() {
    setBusy(true)
    setErr('')
    try {
      const j = await api.start(i18n.language, partner)
      nav(`/j/${j.journey_id}`)
    } catch {
      setErr(t('network'))
      setBusy(false)
    }
  }

  const steps = [
    { icon: MessageCircle, title: t('stepAdvisor'), body: 'Chat or speak in your language' },
    { icon: Receipt, title: t('stepQuote'), body: 'One clear monthly price' },
    { icon: FileCheck2, title: t('stepKyc'), body: 'GSTIN, DigiLocker, photo check' },
    { icon: Bell, title: t('stepTrack'), body: 'Live status, no calls needed' },
  ]

  return (
    <div className="flex flex-col gap-6 px-4 py-6">
      {partner && (
        <div className="rounded-xl bg-warn-soft px-3 py-2 text-sm text-warn">
          {t('partnerMode')}: <b>{partner}</b>
        </div>
      )}
      <section className="flex flex-col gap-3">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">{t('tagline')}</p>
        <h1 className="text-3xl font-bold leading-tight sm:text-4xl">{t('heroTitle')}</h1>
        <p className="text-muted">{t('heroBody')}</p>
      </section>

      <section className="card flex flex-col gap-3 p-4">
        <p className="text-sm font-medium">{t('chooseLanguage')}</p>
        <div className="flex flex-wrap gap-2">
          {LANGS.map((l) => (
            <button
              key={l.code}
              onClick={() => setLanguage(l.code)}
              className={`chip ${i18n.language === l.code ? 'border-brand! bg-brand-soft text-brand' : ''}`}
            >
              {l.label}
            </button>
          ))}
        </div>
        <button className="btn btn-primary mt-1 w-full text-lg" onClick={start} disabled={busy}>
          {busy ? '…' : t('start')}
        </button>
        {err && <p className="text-sm text-bad">{err}</p>}
      </section>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {steps.map(({ icon: Icon, title, body }) => (
          <div key={title} className="card flex flex-col gap-1 p-3">
            <Icon size={20} className="text-brand" aria-hidden />
            <p className="font-semibold">{title}</p>
            <p className="text-xs text-muted">{body}</p>
          </div>
        ))}
      </section>

      <form
        className="card flex items-center gap-2 p-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (orderId.trim()) nav(`/track/${orderId.trim().toUpperCase()}`)
        }}
      >
        <Search size={18} className="text-muted" aria-hidden />
        <input
          value={orderId}
          onChange={(e) => setOrderId(e.target.value)}
          placeholder={`${t('trackOrder')} · ${t('orderId')}`}
          className="min-w-0 flex-1 bg-transparent outline-none"
          aria-label={t('orderId')}
        />
        <button className="btn btn-ghost px-3 py-1.5 text-sm">{t('go')}</button>
      </form>
    </div>
  )
}
