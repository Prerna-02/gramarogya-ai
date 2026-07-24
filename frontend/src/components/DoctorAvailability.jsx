const initials = (name = '') => name.replace(/^Dr\.\s*/i, '').split(/\s+/).slice(0, 2).map((part) => part[0]).join('')

export default function DoctorAvailability({ doctor, compact = false }) {
  if (!doctor) return null
  return <div className={`pt-doctor ${compact ? 'compact' : ''}`}>
    <div className="pt-doctor-avatar">{initials(doctor.name)}</div>
    <div className="pt-doctor-copy">
      <strong>{doctor.name}</strong>
      <span>{doctor.speciality}{!compact && doctor.qualification ? ` · ${doctor.qualification}` : ''}</span>
      <small>{doctor.consultation_time}</small>
    </div>
    <span className={`pt-doctor-status ${doctor.availability_tone}`}>{doctor.availability_status}</span>
  </div>
}
