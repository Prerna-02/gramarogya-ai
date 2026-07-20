import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api.js'
import FacilityCard from '../../components/FacilityCard.jsx'
import { useI18n } from '../../i18n.jsx'

const QUICK = [
  { icon: '🏥', key: 'qa_find', to: '/patient/search', cls: 'q-green' },
  { icon: '🚑', key: 'qa_emergency', to: '/patient/emergency', cls: 'q-red' },
  { icon: '⚠️', key: 'qa_outbreak', to: '/patient/emergency', cls: 'q-amber' },
  { icon: '📞', key: 'qa_ambulance', to: '/patient/emergency', cls: 'q-blue' },
]

export default function PatientHomePage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [facilities, setFacilities] = useState([])

  useEffect(() => { api.facilities().then((d) => setFacilities(d.facilities)).catch(() => {}) }, [])

  const best = facilities.find((f) => f.best_match) || facilities[0]
  const others = facilities.filter((f) => f !== best)

  return (
    <div className="pt-page">
      <div className="pt-hello">
        <div className="pt-hello-text">
          <h1>{t('greeting')} 👋</h1>
          <p>{t('how_help')}</p>
        </div>
      </div>

      <button className="pt-search" onClick={() => navigate('/patient/search')}>
        <span>🔍</span> {t('search_ph')}
      </button>

      <button className="pt-hero" onClick={() => navigate('/patient/search')}>
        <div className="pt-hero-text">
          <h2>{t('find_hospital')}</h2>
          <p>{t('find_hospital_sub')}</p>
        </div>
        <span className="pt-hero-ic">🏩</span>
      </button>

      <h3 className="pt-section">{t('quick_access')}</h3>
      <div className="pt-quick">
        {QUICK.map((q) => (
          <button key={q.key} className={`pt-qtile ${q.cls}`} onClick={() => navigate(q.to)}>
            <span className="pt-qic">{q.icon}</span>
            <span>{t(q.key)}</span>
          </button>
        ))}
      </div>

      {best && (<>
        <h3 className="pt-section">{t('recommended')}</h3>
        <FacilityCard f={best} best />
      </>)}

      {others.length > 0 && (<>
        <h3 className="pt-section">{t('other_nearby')}</h3>
        {others.map((f) => <FacilityCard key={f.id} f={f} />)}
      </>)}

      <p className="pt-disclaimer">{t('disclaimer')}</p>
    </div>
  )
}
