import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../../api.js'
import DoctorAvailability from '../../components/DoctorAvailability.jsx'
import { useI18n } from '../../i18n.jsx'

export default function FacilityDetailsPage() {
  const { t } = useI18n()
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [f, setF] = useState(null)
  const [error, setError] = useState('')

  const specialities = searchParams.getAll('speciality')
  const specialityKey = specialities.join('|')

  useEffect(() => {
    const requestedSpecialities = specialityKey ? specialityKey.split('|') : []
    api.facilityDetail(id, requestedSpecialities).then(setF).catch((e) => setError(e.message))
  }, [id, specialityKey])

  if (error) return <div className="pt-page"><p className="pt-muted">{error}</p></div>
  if (!f) return <div className="pt-page"><p className="pt-muted">…</p></div>

  const exactSpecialists = f.matched_doctors?.filter((doctor) => doctor.speciality === specialities[0]) || []
  const recommendedDoctors = exactSpecialists.length ? exactSpecialists : (f.matched_doctors?.slice(0, 1) || [])
  const recommendedIds = new Set(recommendedDoctors.map((doctor) => doctor.doctor_id))

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

      {specialities.length > 0 && <>
        <h3 className="pt-section">Recommended for your problem</h3>
        <div className="pt-doctor-list recommended">
          {recommendedDoctors.length ? recommendedDoctors.map((doctor) => <DoctorAvailability key={doctor.doctor_id} doctor={doctor} />) :
            <p className="pt-muted">No matching specialist is listed. Please call the hospital before travelling.</p>}
        </div>
      </>}

      <h3 className="pt-section">{specialities.length ? 'Other available doctors' : 'Doctors and consultation times'}</h3>
      <div className="pt-doctor-list">
        {f.doctors?.length ? f.doctors.filter((doctor) => !recommendedIds.has(doctor.doctor_id))
          .map((doctor) => <DoctorAvailability key={doctor.doctor_id} doctor={doctor} />) :
          <p className="pt-muted">Call the hospital to confirm doctor availability.</p>}
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
