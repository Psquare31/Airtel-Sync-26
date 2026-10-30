import { KeyRound, Phone, UserPlus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { LearningPanel } from '../components/LearningPanel'
import { inr } from '../i18n'

interface Summary {
  funnel: { stage: string; count: number }[]
  activation_rate: number
  avg_days_to_activate: number
  avg_followups: number
  cac_per_activation: number
  churn_6m: number
  live_journeys: number
  live_ordered: number
  live_handoffs: number
  model_auc: number
  model_factors: { feature: string; weight: number }[]
}

interface Lead {
  lead_id: string
  source: string
  business_name: string
  segment: string | null
  city: string | null
  stage: string
  reason: string | null
  action: string
  score: number
  contact?: string
  language?: string
  live: boolean
  why: string[]
  assigned: string | null
  monthly_value?: number | null
}

const SEGMENTS = ['Micro retail & services', 'Professional offices', 'Small multi-site businesses', 'Small manufacturers']
// single-series magnitude: one hue, kept apart from brand red and status colours
const BAR = '#3b6ea8'

export default function Backoffice() {
  const [key, setKey] = useState(() => {
    try {
      return sessionStorage.getItem('bo-key') || ''
    } catch {
      return ''
    }
  })
  const [draft, setDraft] = useState('')
  const [summary, setSummary] = useState<Summary | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [reasons, setReasons] = useState<string[]>([])
  const [segment, setSegment] = useState('')
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    if (!key) return
    try {
      const qs = new URLSearchParams({ limit: '40', ...(segment && { segment }), ...(reason && { reason }) })
      const [s, l] = await Promise.all([
        api.backoffice<Summary>('/summary', key),
        api.backoffice<{ leads: Lead[]; reasons: string[] }>(`/leads?${qs}`, key),
      ])
      setSummary(s)
      setLeads(l.leads)
      setReasons(l.reasons)
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'error')
      if (String(e).includes('key')) setKey('')
    }
  }, [key, segment, reason])

  useEffect(() => {
    load()
  }, [load])

  async function assign(lead: Lead, to: string) {
    await api.backoffice(`/leads/${lead.lead_id}/assign`, key, {
      method: 'POST',
      body: JSON.stringify({ assigned_to: to, channel: to.startsWith('Partner') ? 'partner' : 'field' }),
    })
    load()
  }

  if (!key)
    return (
      <form
        className="mx-auto flex w-full max-w-sm flex-col gap-3 px-4 py-10"
        onSubmit={(e) => {
          e.preventDefault()
          setKey(draft)
          try {
            sessionStorage.setItem('bo-key', draft)
          } catch {
            /* ignore */
          }
        }}
      >
        <KeyRound className="text-brand" />
        <h1 className="text-xl font-bold">Sales &amp; partner back-office</h1>
        <p className="text-sm text-muted">Staff access only. Demo key: demo</p>
        <input value={draft} onChange={(e) => setDraft(e.target.value)} type="password" className="rounded-lg border border-line px-3 py-2" placeholder="Access key" />
        <button className="btn btn-primary">Open</button>
        {err && <p className="text-sm text-bad">{err}</p>}
      </form>
    )

  const max = summary?.funnel[0]?.count || 1
  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      <h1 className="text-xl font-bold">Leads the advisor couldn't close</h1>
      {summary && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Lead → activation (Apr–Jun)" value={`${(summary.activation_rate * 100).toFixed(1)}%`} />
            <Stat label="Days to activate" value={String(summary.avg_days_to_activate)} />
            <Stat label="CAC per activation" value={inr(summary.cac_per_activation)} />
            <Stat label="Live digital journeys" value={`${summary.live_journeys}`} sub={`${summary.live_ordered} ordered · ${summary.live_handoffs} need help`} />
          </div>
          <section className="card p-4">
            <h2 className="mb-2 text-sm font-semibold">Baseline funnel, Apr–Jun 2026 (leads)</h2>
            <div className="flex flex-col gap-[2px]" role="list">
              {summary.funnel.map((f, i) => {
                const prev = i ? summary.funnel[i - 1].count : null
                const pct = prev ? Math.round((f.count / prev) * 100) : null
                return (
                  <div key={f.stage} role="listitem" className="group grid grid-cols-[7.5rem_1fr_3.5rem] items-center gap-2 text-xs" title={`${f.stage}: ${f.count.toLocaleString('en-IN')} leads${pct ? ` (${pct}% of previous stage)` : ''}`}>
                    <span className="text-muted">{f.stage}</span>
                    <span className="h-4 rounded-r-[4px]" style={{ width: `${Math.max((f.count / max) * 100, 1)}%`, background: BAR, opacity: 0.9 }} />
                    <span className="text-right tabular-nums">
                      {f.count.toLocaleString('en-IN')}
                      {pct !== null && <span className="block text-[10px] text-muted">{pct}%</span>}
                    </span>
                  </div>
                )
              })}
            </div>
            <p className="mt-2 text-xs text-muted">
              Propensity model (logistic regression, 5-fold AUC {summary.model_auc}) ranks recoverable leads below.
            </p>
          </section>
        </>
      )}

      <LearningPanel staffKey={key} />

      <div className="flex flex-wrap gap-2">
        <select value={segment} onChange={(e) => setSegment(e.target.value)} className="rounded-lg border border-line bg-white px-2 py-1.5 text-sm">
          <option value="">All segments</option>
          {SEGMENTS.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select value={reason} onChange={(e) => setReason(e.target.value)} className="rounded-lg border border-line bg-white px-2 py-1.5 text-sm">
          <option value="">All drop reasons</option>
          {reasons.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </div>
      {err && <p className="text-sm text-bad">{err}</p>}

      <ul className="flex flex-col gap-2">
        {leads.map((l) => (
          <li key={l.lead_id} className={`card flex flex-col gap-2 p-3 ${l.live ? 'border-brand' : ''}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold">
                  {l.business_name} {l.live && <span className="ml-1 rounded bg-brand-soft px-1.5 py-0.5 text-[10px] text-brand">LIVE</span>}
                </p>
                <p className="text-xs text-muted">
                  {l.lead_id} · {l.segment ?? 'Segment unknown'} · {l.city ?? ''} · {l.source}
                  {l.language ? ` · ${l.language}` : ''}
                </p>
              </div>
              <div className="w-20 shrink-0 text-right" title={`Propensity to activate: ${(l.score * 100).toFixed(0)}%`}>
                <p className="text-sm font-semibold tabular-nums">{(l.score * 100).toFixed(0)}%</p>
                <div className="mt-1 h-1.5 w-full rounded-full bg-line">
                  <div className="h-1.5 rounded-full" style={{ width: `${l.score * 100}%`, background: BAR }} />
                </div>
              </div>
            </div>
            <p className="text-sm">
              <span className="text-muted">Stopped at:</span> {l.stage} · {l.reason}
            </p>
            <p className="text-sm">
              <span className="text-muted">Next best action:</span> <b>{l.action}</b>
            </p>
            {l.why.length > 0 && <p className="text-xs text-muted">{l.why.join(' · ')}</p>}
            <div className="flex flex-wrap items-center gap-2">
              {l.assigned ? (
                <span className="rounded-full bg-ok-soft px-2 py-0.5 text-xs text-ok">Assigned to {l.assigned}</span>
              ) : (
                <>
                  <button className="chip flex items-center gap-1" onClick={() => assign(l, 'Field sales')}>
                    <Phone size={12} /> Field sales
                  </button>
                  <button className="chip flex items-center gap-1" onClick={() => assign(l, 'Partner: nearest store')}>
                    <UserPlus size={12} /> Channel partner
                  </button>
                </>
              )}
              {l.contact && <span className="text-xs text-muted">Contact: {l.contact}</span>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="text-xl font-bold tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted">{sub}</p>}
    </div>
  )
}
