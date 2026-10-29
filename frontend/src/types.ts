import type { Check } from './api'

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface QuoteItem {
  product_id: string
  name: string
  category: string
  description: string
  unit: string
  qty: number
  unit_price: number
  monthly: number
  setup: number
  term_months: number
  install_days: number
  selected: boolean
  core: boolean
  locked: boolean
  lock_reason?: string | null
  reason?: string
  reason_code?: string
}

export interface Quote {
  contract_months: number
  contract_options: number[]
  items: QuoteItem[]
  monthly_total: number
  monthly_gst: number
  monthly_with_gst: number
  setup_total: number
  setup_emi: boolean
  setup_emi_monthly: number
  first_bill_estimate: number
  longest_term_months: number
  activation_days: number
  messages: string[]
}

export interface ConsentPurpose {
  required: boolean
  title: string
  text: string
  retention: string
}

export interface KycResult {
  outcome: 'verified' | 'fixable' | 'blocked'
  checks: Check[]
  business_name?: string
  registry?: Record<string, Record<string, string>>
}

export type Pending =
  | { kind: 'chat' }
  | { kind: 'quote'; quote: Quote }
  | {
      kind: 'consent'
      version: string
      purposes: Record<string, ConsentPurpose>
      processors: string[]
      grievance: string
    }
  | {
      kind: 'kyc'
      required: string[]
      optional: string[]
      labels: Record<string, string>
      needs_gstin: boolean
      last_result: KycResult | null
      attempts: number
    }
  | { kind: 'esign'; quote: Quote; business?: string; error?: string | null }

export interface Journey {
  journey_id: string
  stage: string
  lang: string
  messages: Message[]
  profile: Record<string, unknown> | null
  missing: string[]
  recommendation: { segment: string; notes: string[]; eligible: boolean } | null
  explanation: { summary: string; why: Record<string, string>; model: string } | null
  quote: Quote | null
  consent: { granted: boolean } | null
  kyc_result: KycResult | null
  order_id: string | null
  handoff: { reason: string; note: string } | null
  pending: Pending | null
  model: string | null
}

export interface OrderView {
  id: string
  business_name?: string
  timeline: { key: string; label: string; eta: string; done_at: string | null }[]
  current: string
  eta: string
  complete: boolean
  items: { product_id: string; name: string; qty: number; status: string; install_days: number }[]
  notifications: { at: string; channel: string; text: string }[]
  monthly_total: number
  monthly_with_gst: number
  install_slot?: string | null
}
