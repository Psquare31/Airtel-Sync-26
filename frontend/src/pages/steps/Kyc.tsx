import { AlertTriangle, Camera, CheckCircle2, CloudDownload, FileText, Loader2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type Check, type RegistryResult, type UdyamResult, type UploadResult } from '../../api'
import type { StepProps } from '../JourneyPage'

const SAMPLES = ['K01', 'K02', 'K03', 'K04', 'K05', 'K06', 'K07', 'K08', 'K09', 'K10', 'K11', 'K12']
const GSTIN_RE = /^[0-9]{2}[A-Z0-9]{10}[0-9A-Z]Z[0-9A-Z]$/
const UDYAM_RE = /^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$/

export default function Kyc({ journey, resume, busy }: StepProps) {
  const { t } = useTranslation()
  const p = journey.pending
  const [docs, setDocs] = useState<Record<string, UploadResult>>({})
  const [working, setWorking] = useState<string | null>(null)
  const [gstin, setGstin] = useState('')
  const [udyam, setUdyam] = useState('')
  const [lookup, setLookup] = useState<RegistryResult | null>(null)
  const [udyamLookup, setUdyamLookup] = useState<UdyamResult | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    const g = gstin.trim().toUpperCase()
    if (!GSTIN_RE.test(g)) {
      setLookup(null)
      return
    }
    const h = setTimeout(() => api.gstin(g).then(setLookup).catch(() => setLookup(null)), 300)
    return () => clearTimeout(h)
  }, [gstin])

  useEffect(() => {
    const u = udyam.trim().toUpperCase()
    if (!UDYAM_RE.test(u)) {
      setUdyamLookup(null)
      return
    }
    const h = setTimeout(() => api.udyam(u).then(setUdyamLookup).catch(() => setUdyamLookup(null)), 300)
    return () => clearTimeout(h)
  }, [udyam])

  if (p?.kind !== 'kyc') return null
  const docTypes = [...p.required, ...p.optional]
  const result = p.last_result

  async function upload(docType: string, file?: File, specimen?: string) {
    setWorking(docType)
    setErr('')
    try {
      const r = await api.upload(journey.journey_id, docType, file, specimen)
      setDocs((d) => ({ ...d, [docType]: r }))
    } catch (e) {
      setErr(e instanceof Error ? e.message : t('network'))
    } finally {
      setWorking(null)
    }
  }

  async function loadApplicant(id: string) {
    for (const d of docTypes) {
      try {
        await upload(d, undefined, id)
      } catch {
        /* specimen missing for this doc */
      }
    }
  }

  async function digilocker() {
    setWorking('digilocker')
    setErr('')
    try {
      const r = await api.digilocker(journey.journey_id, gstin.trim() || undefined, udyam.trim() || undefined)
      setDocs((d) => Object.fromEntries([...Object.entries(d), ...r.documents.map((x) => [x.doc_type, x])]))
    } catch (e) {
      setErr(e instanceof Error ? e.message : t('network'))
    } finally {
      setWorking(null)
    }
  }

  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      <div>
        <h1 className="text-xl font-bold">{t('kycTitle')}</h1>
        <p className="text-muted">{t('kycBody')}</p>
      </div>

      {result && <ResultPanel result={result} />}

      <section className="card flex flex-col gap-2 p-4">
        <p className="font-semibold">Your registration numbers</p>
        <p className="text-xs text-muted">Checked live against the GST and Udyam registries.</p>
        <input
          value={gstin}
          onChange={(e) => setGstin(e.target.value.toUpperCase())}
          placeholder="GSTIN (15 characters)"
          className="rounded-lg border border-line px-3 py-2 font-mono uppercase placeholder:normal-case placeholder:font-sans"
          maxLength={15}
          aria-label="GSTIN"
        />
        {lookup && (
          <p className={`text-sm ${lookup.found && lookup.status === 'Active' ? 'text-ok' : 'text-bad'}`}>
            {!lookup.valid_format
              ? lookup.problems?.join('. ')
              : !lookup.found
                ? 'Not found in the GST registry'
                : `${lookup.trade_name} · ${lookup.status} · ${lookup.state}`}
          </p>
        )}
        <input
          value={udyam}
          onChange={(e) => setUdyam(e.target.value.toUpperCase())}
          placeholder="Udyam number, if registered: UDYAM-XX-00-0000000"
          className="rounded-lg border border-line px-3 py-2 font-mono uppercase placeholder:normal-case placeholder:font-sans"
          maxLength={19}
          aria-label="Udyam number"
        />
        {udyamLookup && (
          <p className={`text-sm ${udyamLookup.found ? 'text-ok' : 'text-bad'}`}>
            {!udyamLookup.valid_format
              ? udyamLookup.problems?.join('. ')
              : !udyamLookup.found
                ? 'Not found in the Udyam registry'
                : `${udyamLookup.enterprise_name} · ${udyamLookup.enterprise_type} enterprise · ${udyamLookup.city}`}
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        {docTypes.map((d) => (
          <DocCard
            key={d}
            label={p.labels[d]}
            optional={p.optional.includes(d)}
            doc={docs[d]}
            failed={result?.checks.filter((c) => c.doc === d && c.status !== 'pass') ?? []}
            working={working === d}
            onFile={(f) => upload(d, f)}
          />
        ))}
      </section>

      <button
        className="flex items-center gap-2 self-start text-sm text-muted underline-offset-2 hover:underline"
        onClick={digilocker}
        disabled={!gstin.trim() || working !== null}
        title="Enter your GSTIN above first"
      >
        {working === 'digilocker' ? <Loader2 className="animate-spin" size={16} /> : <CloudDownload size={16} />}
        Or fetch the GST and Udyam certificates from DigiLocker
      </button>

      <details className="card p-3 text-sm">
        <summary className="cursor-pointer font-medium">{t('useSample')} (demo specimen documents)</summary>
        <div className="mt-2 flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <button key={s} className="chip" onClick={() => loadApplicant(s)} disabled={working !== null}>
              {s}
            </button>
          ))}
        </div>
      </details>

      {err && <p className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad">{err}</p>}

      <button
        className="btn btn-primary w-full"
        disabled={busy || working !== null}
        onClick={() => resume({ kind: 'kyc', action: 'submit', gstin: gstin.trim() || undefined, udyam_number: udyam.trim() || undefined })}
      >
        {busy ? (
          <>
            <Loader2 className="animate-spin" size={18} /> {t('verifying')}
          </>
        ) : (
          t('verifyNow')
        )}
      </button>
      <button className="btn btn-ghost w-full" disabled={busy} onClick={() => resume({ kind: 'kyc', action: 'assisted' })}>
        {t('partnerHelp')}
      </button>
    </div>
  )
}

function DocCard({ label, optional, doc, failed, working, onFile }: {
  label: string
  optional: boolean
  doc?: UploadResult
  failed: Check[]
  working: boolean
  onFile: (f: File) => void
}) {
  const { t } = useTranslation()
  const docFails = doc?.checks.filter((c) => c.status === 'fail') ?? []
  const state = working ? 'working' : docFails.length || failed.some((c) => c.status === 'fail') ? 'bad' : doc ? 'ok' : 'empty'
  return (
    <div className={`card flex flex-col gap-2 p-3 ${state === 'bad' ? 'border-bad' : state === 'ok' ? 'border-ok' : ''}`}>
      <div className="flex items-center gap-3">
        {state === 'working' ? (
          <Loader2 className="animate-spin text-muted" size={20} />
        ) : state === 'ok' ? (
          <CheckCircle2 className="text-ok" size={20} />
        ) : state === 'bad' ? (
          <XCircle className="text-bad" size={20} />
        ) : (
          <FileText className="text-muted" size={20} />
        )}
        <div className="min-w-0 flex-1">
          <p className="font-medium">
            {label} {optional && <span className="text-xs text-muted">(if Udyam-registered)</span>}
          </p>
          {working ? (
            <p className="text-xs text-muted">Reading your document… this can take up to 30 seconds</p>
          ) : (
            doc && (
              <p className="truncate text-xs text-muted">
                {doc.source === 'digilocker' ? 'DigiLocker · issuer-verified' : `Read by ${doc.extractor}`}
              </p>
            )
          )}
        </div>
        <label className="btn btn-ghost cursor-pointer px-3 py-1.5 text-sm">
          <Camera size={16} /> {doc ? 'Redo' : t('upload')}
          <input
            type="file"
            accept="image/*"
            capture="environment"
            className="sr-only"
            onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
          />
        </label>
      </div>
      {doc && Object.keys(doc.fields).length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-lg bg-paper px-3 py-2 text-xs">
          {Object.entries(doc.fields)
            .filter(([, v]) => v)
            .map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k.replace(/_/g, ' ')}</dt>
                <dd className="break-words font-medium">{v}</dd>
              </div>
            ))}
        </dl>
      )}
      {[...docFails, ...failed].map((c, i) => (
        <p key={c.id + i} className={`text-sm ${c.status === 'fail' ? 'text-bad' : 'text-warn'}`}>
          {c.message}
        </p>
      ))}
    </div>
  )
}

function ResultPanel({ result }: { result: NonNullable<Extract<StepProps['journey']['pending'], { kind: 'kyc' }>['last_result']> }) {
  const { t } = useTranslation()
  const fails = result.checks.filter((c) => c.status === 'fail')
  const passes = result.checks.filter((c) => c.status === 'pass')
  return (
    <section className={`card flex flex-col gap-2 p-4 ${result.outcome === 'blocked' ? 'border-bad bg-bad-soft' : 'border-warn bg-warn-soft'}`}>
      <p className="flex items-center gap-2 font-semibold">
        <AlertTriangle size={18} aria-hidden /> {result.outcome === 'blocked' ? t('kycBlocked') : t('kycIssues')}
      </p>
      <ul className="flex flex-col gap-1 text-sm">
        {fails.map((c) => (
          <li key={c.id} className="flex gap-2">
            <XCircle size={16} className="mt-0.5 shrink-0 text-bad" /> {c.message}
          </li>
        ))}
        {passes.map((c) => (
          <li key={c.id} className="flex gap-2 text-muted">
            <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-ok" /> {c.message}
          </li>
        ))}
      </ul>
    </section>
  )
}
