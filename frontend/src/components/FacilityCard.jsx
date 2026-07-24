import { useNavigate } from 'react-router-dom'

import { useI18n } from '../i18n.jsx'
import DoctorAvailability from './DoctorAvailability.jsx'

export default function FacilityCard({ f, best }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const doctor = f.matched_doctors?.[0] || f.doctors?.find((item) => item.availability_tone === 'available') || f.doctors?.[0]
  const openDetails = () => {
    const query = new URLSearchParams()
    f.required_specialities?.forEach((speciality) => query.append('speciality', speciality))
    navigate(`/patient/facility/${f.id}${query.size ? `?${query}` : ''}`)
  }
  return (
    <div className={`pt-fac ${best ? 'best' : ''}`} onClick={openDetails}>
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
      {doctor && <DoctorAvailability doctor={doctor} compact />}
      <div className="pt-fac-foot">
        <span className={`pt-status ${f.status}`}>{t(`st_${f.status}`)}</span>
        <span className="pt-link">{t('view_details')} →</span>
      </div>
    </div>
  )
}
