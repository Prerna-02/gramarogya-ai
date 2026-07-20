import { useNavigate } from 'react-router-dom'

import { useI18n } from '../i18n.jsx'

export default function FacilityCard({ f, best }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  return (
    <div className={`pt-fac ${best ? 'best' : ''}`} onClick={() => navigate(`/patient/facility/${f.id}`)}>
      <div className="pt-fac-top">
        <div>
          <div className="pt-fac-name">{f.name}</div>
          <div className="pt-fac-type">{f.type}</div>
        </div>
        {best && <span className="pt-best">★ {t('best_match')}</span>}
      </div>
      <div className="pt-fac-meta">
        <span>📍 {f.distance_km} {t('km')}</span>
        <span>⏱ {f.waiting_time_min} {t('min')}</span>
        <span>🛏 {f.beds_available}</span>
      </div>
      <div className="pt-fac-foot">
        <span className={`pt-status ${f.status}`}>{t(`st_${f.status}`)}</span>
        <span className="pt-link">{t('view_details')} →</span>
      </div>
    </div>
  )
}
