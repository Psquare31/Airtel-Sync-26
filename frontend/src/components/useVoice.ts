import { useRef, useState } from 'react'
import { api } from '../api'

type SpeechRec = {
  lang: string
  interimResults: boolean
  onresult: (e: { results: { 0: { transcript: string } }[] }) => void
  onend: () => void
  onerror: () => void
  start: () => void
  stop: () => void
}

const BCP47: Record<string, string> = { en: 'en-IN', hi: 'hi-IN', ta: 'ta-IN', mr: 'mr-IN', hinglish: 'hi-IN' }

/** Records speech; transcribes with Whisper on the server, falls back to the browser recogniser. */
export function useVoice(lang: string, onText: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const [working, setWorking] = useState(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const browserRec = useRef<SpeechRec | null>(null)

  function browserFallback() {
    const Ctor = (window as unknown as { SpeechRecognition?: new () => SpeechRec; webkitSpeechRecognition?: new () => SpeechRec })
    const Rec = Ctor.SpeechRecognition || Ctor.webkitSpeechRecognition
    if (!Rec) return false
    const rec = new Rec()
    rec.lang = BCP47[lang] || 'en-IN'
    rec.interimResults = false
    rec.onresult = (e) => onText(e.results[0][0].transcript)
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    browserRec.current = rec
    rec.start()
    setListening(true)
    return true
  }

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      browserFallback()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const chunks: Blob[] = []
      const mr = new MediaRecorder(stream)
      mr.ondataavailable = (e) => chunks.push(e.data)
      mr.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop())
        setListening(false)
        setWorking(true)
        try {
          const { text } = await api.transcribe(new Blob(chunks, { type: mr.mimeType }), lang === 'hinglish' ? 'hi' : lang)
          if (text.trim()) onText(text.trim())
        } catch {
          browserFallback()
        } finally {
          setWorking(false)
        }
      }
      recorder.current = mr
      mr.start()
      setListening(true)
      setTimeout(() => mr.state === 'recording' && mr.stop(), 15000)
    } catch {
      browserFallback()
    }
  }

  function stop() {
    if (recorder.current?.state === 'recording') recorder.current.stop()
    browserRec.current?.stop()
  }

  return { listening, working, toggle: () => (listening ? stop() : start()) }
}

export function speak(text: string, lang: string) {
  if (!('speechSynthesis' in window)) return
  const u = new SpeechSynthesisUtterance(text)
  u.lang = BCP47[lang] || 'en-IN'
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(u)
}
