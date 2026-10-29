import { Loader2, Mic, Send, Square, Volume2, VolumeX } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { speak, useVoice } from '../../components/useVoice'
import type { StepProps } from '../JourneyPage'

const CHIPS: Record<string, { en: string; hi: string }[]> = {
  business_type: [
    { en: 'Kirana store', hi: 'किराना दुकान' },
    { en: 'Clinic', hi: 'क्लिनिक' },
    { en: 'CA office', hi: 'CA ऑफिस' },
    { en: 'Restaurant chain', hi: 'रेस्टोरेंट चेन' },
    { en: 'Small factory', hi: 'छोटी फैक्ट्री' },
    { en: 'Salon', hi: 'सैलून' },
  ],
  employees: [
    { en: 'Just me', hi: 'सिर्फ़ मैं' },
    { en: '3 people', hi: '3 लोग' },
    { en: '10 people', hi: '10 लोग' },
    { en: '30 people', hi: '30 लोग' },
  ],
  sites: [
    { en: '1 location', hi: '1 दुकान' },
    { en: '2 locations', hi: '2 दुकान' },
    { en: '5 branches', hi: '5 ब्रांच' },
  ],
  city: ['Mumbai', 'Delhi', 'Bengaluru', 'Pune', 'Jaipur', 'Lucknow', 'Kochi'].map((c) => ({ en: c, hi: c })),
  has_gstin: [
    { en: 'Yes, I have GST', hi: 'हाँ, GST है' },
    { en: 'No GST yet', hi: 'GST नहीं है' },
  ],
  needs: [
    { en: 'Internet for UPI and billing', hi: 'UPI और बिलिंग के लिए इंटरनेट' },
    { en: 'WhatsApp for customers', hi: 'ग्राहकों के लिए WhatsApp' },
    { en: 'CCTV', hi: 'CCTV कैमरा' },
    { en: 'Business email', hi: 'बिज़नेस ईमेल' },
    { en: 'Backup internet', hi: 'बैकअप इंटरनेट' },
    { en: 'Wi-Fi for customers', hi: 'ग्राहकों के लिए Wi-Fi' },
  ],
}

export default function Advisor({ journey, resume, busy }: StepProps) {
  const { t, i18n } = useTranslation()
  const [text, setText] = useState('')
  const [voiceOut, setVoiceOut] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const lang = i18n.language
  const send = async (msg: string) => {
    const m = msg.trim()
    if (!m || busy) return
    setText('')
    const j = await resume({ kind: 'chat', text: m })
    const last = j?.messages.at(-1)
    if (voiceOut && last?.role === 'assistant') speak(last.content, lang)
  }
  const voice = useVoice(lang, (spoken) => send(spoken))

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [journey.messages.length, busy])

  const nextSlot = journey.missing?.[0]
  const chips = (nextSlot && CHIPS[nextSlot]) || []

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {journey.messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <p
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed ${
                m.role === 'user' ? 'rounded-br-md bg-brand text-white' : 'rounded-bl-md border border-line bg-white'
              }`}
            >
              {m.content}
            </p>
          </div>
        ))}
        {busy && (
          <div className="typing flex gap-1 px-2 text-2xl leading-none text-muted" aria-label="typing">
            <span>•</span>
            <span>•</span>
            <span>•</span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="sticky bottom-0 border-t border-line bg-paper/95 px-4 pb-[max(env(safe-area-inset-bottom),12px)] pt-2 backdrop-blur">
        {chips.length > 0 && (
          <div className="-mx-4 mb-2 flex gap-2 overflow-x-auto px-4 pb-1">
            {chips.map((c) => {
              const label = lang === 'hi' || lang === 'mr' ? c.hi : c.en
              return (
                <button key={c.en} className="chip" onClick={() => send(label)} disabled={busy}>
                  {label}
                </button>
              )
            })}
          </div>
        )}
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            send(text)
          }}
        >
          <button
            type="button"
            onClick={() => setVoiceOut((v) => !v)}
            className="rounded-full p-2 text-muted hover:bg-white"
            aria-label={voiceOut ? 'Turn off spoken replies' : 'Read replies aloud'}
            title={voiceOut ? 'Spoken replies on' : 'Spoken replies off'}
          >
            {voiceOut ? <Volume2 size={20} /> : <VolumeX size={20} />}
          </button>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={voice.listening ? t('listening') : t('typeMessage')}
            className="min-w-0 flex-1 rounded-full border border-line bg-white px-4 py-2.5 outline-none focus:border-brand"
            aria-label={t('typeMessage')}
            maxLength={500}
          />
          <button
            type="button"
            onClick={voice.toggle}
            className={`rounded-full p-2.5 ${voice.listening ? 'bg-brand text-white' : 'bg-white text-ink'} border border-line`}
            aria-label={voice.listening ? 'Stop recording' : 'Speak'}
            disabled={voice.working}
          >
            {voice.working ? <Loader2 size={20} className="animate-spin" /> : voice.listening ? <Square size={20} /> : <Mic size={20} />}
          </button>
          <button className="btn btn-primary rounded-full p-2.5" aria-label={t('send')} disabled={busy || !text.trim()}>
            <Send size={20} />
          </button>
        </form>
      </div>
    </div>
  )
}
