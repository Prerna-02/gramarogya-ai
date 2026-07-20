import { useEffect, useState } from 'react'

import { api } from '../../api.js'
import FacilityCard from '../../components/FacilityCard.jsx'
import { useI18n } from '../../i18n.jsx'

const SERVICES = [
  { key: 'svc_general', q: null, icon: '🩺' },
  { key: 'svc_fever', q: 'Emergency', icon: '🤒' },
  { key: 'svc_maternity', q: 'Maternity', icon: '🤰' },
  { key: 'svc_trauma', q: 'Trauma', icon: '🩹' },
  { key: 'svc_emergency', q: 'ICU', icon: '🚨' },
]

export default function FacilitySearchPage() {
  const { t } = useI18n()
  const [service, setService] = useState(SERVICES[0])
  const [facilities, setFacilities] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.facilities(service.q).then((d) => setFacilities(d.facilities)).catch(() => {}).finally(() => setLoading(false))
  }, [service])

  return (
    <div className="pt-page">
      <h1 className="pt-h1">{t('choose_service')}</h1>
      <div className="pt-chips">
        {SERVICES.map((s) => (
          <button key={s.key} className={`pt-chip ${service.key === s.key ? 'active' : ''}`} onClick={() => setService(s)}>
            <span>{s.icon}</span> {t(s.key)}
          </button>
        ))}
      </div>

      <h3 className="pt-section">{t('results')}</h3>
      {loading && <p className="pt-muted">…</p>}
      {facilities.map((f) => <FacilityCard key={f.id} f={f} best={f.best_match} />)}
      <p className="pt-disclaimer">{t('call_before')}</p>
    </div>
  )
}
