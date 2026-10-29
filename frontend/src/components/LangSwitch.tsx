import { Languages } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { LANGS, setLanguage } from '../i18n'

export function LangSwitch({ onChange }: { onChange?: (code: string) => void }) {
  const { i18n } = useTranslation()
  return (
    <label className="flex items-center gap-1 text-sm">
      <Languages size={16} className="text-muted" aria-hidden />
      <span className="sr-only">Language</span>
      <select
        value={i18n.language}
        onChange={(e) => {
          setLanguage(e.target.value)
          onChange?.(e.target.value)
          window.dispatchEvent(new CustomEvent('langchange', { detail: e.target.value }))
        }}
        className="rounded-lg border border-line bg-white px-2 py-1"
      >
        {LANGS.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </label>
  )
}
