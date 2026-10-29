import { Link, Route, Routes } from 'react-router-dom'
import { LangSwitch } from './components/LangSwitch'
import Backoffice from './pages/Backoffice'
import Home from './pages/Home'
import JourneyPage from './pages/JourneyPage'
import Tracker from './pages/Tracker'

export default function App() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-3xl flex-col">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-paper/90 px-4 py-3 backdrop-blur">
        <Link to="/" className="flex items-center gap-2 font-bold">
          <img src="/favicon.svg" alt="" className="h-7 w-7" />
          <span>
            Accel <span className="text-brand">Business</span>
          </span>
        </Link>
        <LangSwitch />
      </header>
      <main className="flex flex-1 flex-col">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/j/:id" element={<JourneyPage />} />
          <Route path="/track/:id" element={<Tracker />} />
          <Route path="/backoffice" element={<Backoffice />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>
      <footer className="px-4 py-4 text-center text-xs text-muted">
        Prototype for YTL Hackathon 2026 · Accel Telecom is fictional · All data is synthetic
      </footer>
    </div>
  )
}
