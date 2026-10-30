import { Download, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { API, api } from '../api'

interface Learning {
  feedback_up: number
  feedback_down: number
  top_reasons: [string, number][]
  learned_turns: number
  learned_by_lang: Record<string, number>
  flagged: { journey_id: string; reasons: string[]; comments: string[]; consented: boolean;
             turns: { text: string; updates: Record<string, unknown> }[] }[]
  model: { auc: number; trained_at: string; live_rows: number; lead_rows: number }
}

/** How the advisor and lead scoring improve from consented, real use. */
export function LearningPanel({ staffKey }: { staffKey: string }) {
  const [data, setData] = useState<Learning | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.backoffice<Learning>('/learning', staffKey).then(setData).catch(() => setData(null))
  }, [staffKey])
  useEffect(load, [load])

  async function retrain() {
    setBusy(true)
    try {
      await api.backoffice('/model/retrain', staffKey, { method: 'POST' })
      load()
    } finally {
      setBusy(false)
    }
  }

  async function downloadScenarios() {
    const res = await fetch(`${API}/api/backoffice/learning/scenarios.yaml`, { headers: { 'X-Backoffice-Key': staffKey } })
    const url = URL.createObjectURL(await res.blob())
    const a = Object.assign(document.createElement('a'), { href: url, download: 'learned_scenarios.yaml' })
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!data) return null
  const langs = Object.entries(data.learned_by_lang).map(([l, n]) => `${l} ${n}`).join(' · ') || 'none yet'
  return (
    <section className="card flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">How the advisor is learning</h2>
        <button className="btn btn-ghost px-2.5 py-1.5 text-xs" onClick={retrain} disabled={busy}>
          <RefreshCw size={14} className={busy ? 'animate-spin' : ''} /> Retrain lead model
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <p><ThumbsUp size={14} className="mr-1 inline text-ok" />{data.feedback_up} plans liked</p>
        <p><ThumbsDown size={14} className="mr-1 inline text-bad" />{data.feedback_down} flagged</p>
        <p title="Consented, redacted advisor turns used as prompt examples">{data.learned_turns} learned turns <span className="text-muted">({langs})</span></p>
        <p title={`Trained ${new Date(data.model.trained_at).toLocaleString('en-IN')}`}>
          Lead model AUC {data.model.auc} <span className="text-muted">({data.model.live_rows} live outcomes)</span>
        </p>
      </div>
      {data.top_reasons.length > 0 && (
        <p className="text-xs text-muted">Top reasons: {data.top_reasons.map(([r, n]) => `${r} (${n})`).join(' · ')}</p>
      )}
      {data.flagged.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-medium">Conversations owners flagged ({data.flagged.length})</summary>
          <ul className="mt-2 flex flex-col gap-2">
            {data.flagged.map((f) => (
              <li key={f.journey_id} className="rounded-lg bg-paper p-2">
                <p className="text-xs">
                  <b>{f.journey_id}</b> · {f.reasons.join(', ') || 'thumbs down'}
                  {f.comments.length > 0 && <span className="text-muted"> · “{f.comments.join(' / ')}”</span>}
                </p>
                {f.consented ? (
                  f.turns.map((t, i) => (
                    <p key={i} className="text-xs text-muted">
                      “{t.text}” → {Object.keys(t.updates).join(', ')}
                    </p>
                  ))
                ) : (
                  <p className="text-xs text-muted">Chat not kept: the owner didn't opt in to improvement.</p>
                )}
              </li>
            ))}
          </ul>
          <button className="btn btn-ghost mt-2 px-2.5 py-1.5 text-xs" onClick={downloadScenarios}>
            <Download size={14} /> Draft test scenarios (YAML)
          </button>
        </details>
      )}
    </section>
  )
}
