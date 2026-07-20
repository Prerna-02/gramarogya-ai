import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../../api.js'
import { useI18n } from '../../i18n.jsx'

export default function FacilityDetailsPage() {
  const { t } = useI18n()
  const { id } = useParams()
  const navigate = useNavigate()
  const [f, setF] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api.facilityDetail(id).then(setF).catch((e) => setError(e.message)) }, [id])

  if (error) return <div className="pt-page"><p className="pt-muted">{error}</p></div>
  if (!f) return <div className="pt-page"><p className="pt-muted">…</p></div>

  // Search the map by NAME so the provider's verified geocoding places it,
  // rather than relying on approximate prototype coordinates.
  const maps = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(f.name + ', Gadchiroli, Maharashtra')}`

  return (
    <div className="pt-page">
      <button className="pt-back" onClick={() => navigate(-1)}>← {t('back')}</button>

      <div className="pt-detail-hero">
        <span className={`pt-status ${f.status}`}>{t(`st_${f.status}`)}</span>
        <h1>{f.name}</h1>
        <p>{f.type}</p>
      </div>

      <div className="pt-stat-row">
        <div className="pt-stat"><span>📍</span><b>{f.distance_km}</b>{t('km')}</div>
        <div className="pt-stat"><span>⏱</span><b>{f.waiting_time_min}</b>{t('min')}</div>
        <div className="pt-stat"><span>🛏</span><b>{f.beds_available}</b>{t('beds_available')}</div>
      </div>

      <h3 className="pt-section">{t('services_available')}</h3>
      <div className="pt-tags">
        {f.capabilities.map((c) => <span key={c} className="pt-tag">{c}</span>)}
      </div>

      <div className="pt-actions">
        <a className="pt-btn call" href="tel:108">📞 {t('call')}</a>
        <a className="pt-btn dir" href={maps} target="_blank" rel="noreferrer">🧭 {t('directions')}</a>
      </div>

      {f.data_last_verified_at && (
        <p className="pt-verified">{t('last_verified')}: {new Date(f.data_last_verified_at).toLocaleString()}</p>
      )}
      <p className="pt-disclaimer">{t('prototype_note')}</p>
      <p className="pt-disclaimer">{t('call_before')}</p>
    </div>
  )
}
