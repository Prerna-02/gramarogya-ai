import { useEffect, useState } from 'react'

import { api } from '../../api.js'
import FacilityCard from '../../components/FacilityCard.jsx'
import { SUGGESTIONS, useI18n } from '../../i18n.jsx'

export default function FacilitySearchPage() {
  const { t, lang } = useI18n()
  const [q, setQ] = useState('')
  const [result, setResult] = useState(null)
  const [browse, setBrowse] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => { api.facilities().then((d) => setBrowse(d.facilities)).catch(() => {}) }, [])

  const runTriage = (text, label) => {
    if (!text.trim()) return
    setQ(label ?? text)
    setLoading(true)
    api.triage(text).then(setResult).catch(() => {}).finally(() => setLoading(false))
  }

  const sug = SUGGESTIONS.filter((s) =>
    !q || s[lang]?.toLowerCase().includes(q.toLowerCase()) || s.q.includes(q.toLowerCase()))

  return (
    <div className="pt-page">
      <h1 className="pt-h1">{t('describe_problem')}</h1>

      <div className="pt-searchbar">
        <input value={q} placeholder={t('describe_problem')}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && runTriage(q)} />
        <button onClick={() => runTriage(q)}>{t('search_action')}</button>
      </div>

      <div className="pt-chips">
        {sug.map((s) => (
          <button key={s.q} className="pt-chip" onClick={() => runTriage(s.q, s[lang])}>{s[lang]}</button>
        ))}
      </div>

      {loading && <p className="pt-muted">…</p>}

      {result && !loading && (
        <>
          {result.is_emergency && (
            <div className="pt-emerg-banner">
              <div>⚠️ {t('emergency_now')}</div>
              <a className="pt-emerg-call" href="tel:108">📞 {t('call_108')}</a>
            </div>
          )}
          <div className="pt-note">🛈 {t('no_diagnosis')}</div>
          <h3 className="pt-section">{t('suggested_facilities')}</h3>
          {result.facilities.map((f, i) => <FacilityCard key={f.id} f={f} best={i === 0 && !result.is_emergency} />)}
        </>
      )}

      {!result && !loading && (
        <>
          <h3 className="pt-section">{t('results')}</h3>
          {browse.map((f) => <FacilityCard key={f.id} f={f} best={f.best_match} />)}
        </>
      )}

      <p className="pt-disclaimer">{t('no_diagnosis')} · {t('call_before')}</p>
    </div>
  )
}
