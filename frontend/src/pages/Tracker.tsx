import { CheckCircle2, Circle, Loader2, MessageCircle, Send, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { inr } from '../i18n'
import type { OrderView } from '../types'

export default function Tracker() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const [order, setOrder] = useState<OrderView | null>(null)
  const [err, setErr] = useState('')
  const [q, setQ] = useState('')
  const [answer, setAnswer] = useState('')
  const [asking, setAsking] = useState(false)
  const [privacy, setPrivacy] = useState('')

  useEffect(() => {
    let alive = true
    const load = () => api.order(id).then((o) => alive && setOrder(o)).catch(() => alive && setErr('Order not found'))
    load()
    const h = setInterval(load, 15000)
    return () => {
      alive = false
      clearInterval(h)
    }
  }, [id])

  if (err) return <p className="p-6 text-bad">{err}</p>
  if (!order) return <p className="p-6 text-muted">…</p>

  async function withdrawMsg(purposes: string[]) {
    const r = await api.withdraw(order!.journey_id, purposes)
    return purposes.includes('marketing') ? 'Offers stopped.' : `Erased ${r.documents_erased} document record(s).`
  }

  async function ask(e: React.FormEvent) {
    e.preventDefault()
    if (!q.trim()) return
    setAsking(true)
    try {
      setAnswer((await api.ask(id, q, i18n.language)).answer)
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      <div>
        <p className="text-sm text-muted">
          {t('trackerTitle')} · <span className="font-mono">{order.id}</span>
        </p>
        <h1 className="text-2xl font-bold">{order.current}</h1>
        <p className="text-muted">
          {order.business_name} · {t('expected')} <b>{new Date(order.eta).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</b>
        </p>
      </div>

      <ol className="card flex flex-col gap-0 p-4">
        {order.timeline.map((s, i) => {
          const done = !!s.done_at
          const current = !done && (i === 0 || !!order.timeline[i - 1].done_at)
          return (
            <li key={s.key} className="flex gap-3">
              <div className="flex flex-col items-center">
                {done ? (
                  <CheckCircle2 className="text-ok" size={22} />
                ) : current ? (
                  <Loader2 className="animate-spin text-brand" size={22} />
                ) : (
                  <Circle className="text-line" size={22} />
                )}
                {i < order.timeline.length - 1 && <span className={`w-0.5 flex-1 ${done ? 'bg-ok' : 'bg-line'}`} style={{ minHeight: 20 }} />}
              </div>
              <div className="pb-4">
                <p className={`font-medium ${done || current ? '' : 'text-muted'}`}>{s.label}</p>
                <p className="text-xs text-muted">
                  {done
                    ? new Date(s.done_at!).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
                    : `ETA ${new Date(s.eta).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}`}
                  {s.key === 'scheduled' && order.install_slot ? ` · ${order.install_slot}` : ''}
                </p>
              </div>
            </li>
          )
        })}
      </ol>

      <section className="card flex flex-col gap-2 p-4">
        <h2 className="font-semibold">{t('services')}</h2>
        {order.items.map((i) => (
          <div key={i.product_id} className="flex items-center justify-between gap-2 text-sm">
            <span>
              {i.name} {i.qty > 1 && <span className="text-muted">× {i.qty}</span>}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-xs ${i.status === 'Active' ? 'bg-ok-soft text-ok' : 'bg-warn-soft text-warn'}`}>
              {i.status === 'Active' ? '● ' : '◐ '}
              {i.status}
            </span>
          </div>
        ))}
        <p className="mt-1 border-t border-line pt-2 text-sm">
          {inr(order.monthly_with_gst)}
          {t('perMonth')} <span className="text-muted">({t('inclGst')}) · one bill · support 121</span>
        </p>
      </section>

      <form onSubmit={ask} className="card flex flex-col gap-2 p-4">
        <div className="flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('askOrder')} className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2" maxLength={300} />
          <button className="btn btn-primary px-3" disabled={asking}>
            {asking ? <Loader2 className="animate-spin" size={18} /> : <Send size={18} />}
          </button>
        </div>
        {answer && <p className="rounded-lg bg-paper px-3 py-2 text-sm">{answer}</p>}
      </form>

      <section className="flex flex-col gap-2">
        <h2 className="flex items-center gap-2 font-semibold">
          <MessageCircle size={18} className="text-ok" /> {t('updates')} (WhatsApp)
        </h2>
        {[...order.notifications].reverse().map((n, i) => (
          <div key={i} className="max-w-[90%] rounded-2xl rounded-tl-md bg-[#e7f8df] px-3 py-2 text-sm">
            {n.text}
            <p className="text-right text-[10px] text-muted">{new Date(n.at).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}</p>
          </div>
        ))}
      </section>

      <details className="card p-4 text-sm">
        <summary className="flex cursor-pointer items-center gap-2 font-medium">
          <ShieldCheck size={16} className="text-ok" /> Your data &amp; consent
        </summary>
        <p className="mt-2 text-muted">Document photos were deleted after reading. You can stop offers or erase the extracted KYC details at any time.</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="chip" onClick={async () => setPrivacy(await withdrawMsg(['marketing']))}>
            Stop offers
          </button>
          <button className="chip" onClick={async () => setPrivacy(await withdrawMsg(['kyc_verification']))}>
            Erase my KYC details
          </button>
        </div>
        {privacy && <p className="mt-2 text-ok">{privacy}</p>}
      </details>

      {!order.complete && (
        <button className="btn btn-ghost text-sm" onClick={async () => setOrder(await api.advance(id))}>
          {t('demoAdvance')}
        </button>
      )}
    </div>
  )
}
