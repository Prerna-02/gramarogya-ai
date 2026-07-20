import { useEffect, useState } from 'react'

import { api } from '../../api.js'
import { useI18n } from '../../i18n.jsx'

const NUMBERS = [
  { label: 'Ambulance', num: '108', icon: '🚑' },
  { label: 'Police', num: '100', icon: '🚓' },
  { label: 'Health Helpline', num: '104', icon: '☎️' },
  { label: 'Disaster', num: '112', icon: '🆘' },
]

export default function PatientEmergencyPage() {
  const { t } = useI18n()
  const [alert, setAlert] = useState(null)

  useEffect(() => { api.outbreakAlert().then(setAlert).catch(() => {}) }, [])

  return (
    <div className="pt-page">
      <h1 className="pt-h1">{t('emergency_help')}</h1>

      <a className="pt-sos" href="tel:108">
        <span className="pt-sos-ic">🚑</span>
        <span>{t('call_ambulance')}</span>
      </a>

      <h3 className="pt-section">{t('emergency_numbers')}</h3>
      <div className="pt-numbers">
        {NUMBERS.map((n) => (
          <a key={n.num} className="pt-number" href={`tel:${n.num}`}>
            <span className="pt-num-ic">{n.icon}</span>
            <div><b>{n.num}</b><span>{n.label}</span></div>
          </a>
        ))}
      </div>

      <h3 className="pt-section">{t('outbreak_title')}</h3>
      <div className={`pt-outbreak ${alert?.active ? 'active' : 'calm'}`}>
        <span className="pt-outbreak-ic">{alert?.active ? '⚠️' : '✅'}</span>
        <div>
          <p>{alert ? alert.message : '…'}</p>
          {alert?.as_of && <span className="pt-verified">{t('last_verified')}: {alert.as_of}</span>}
        </div>
      </div>

      <p className="pt-disclaimer">{t('disclaimer')}</p>
    </div>
  )
}
