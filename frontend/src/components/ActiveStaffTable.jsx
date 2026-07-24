export default function ActiveStaffTable({ staff }) {
  if (!staff?.length) return <p className="muted">No current-duty assignments available.</p>
  return (
    <div className="active-staff-list">
      {staff.map((person) => (
        <div className="active-staff-row" key={person.staff_id}>
          <div className="staff-avatar">{person.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</div>
          <div className="staff-person">
            <strong>{person.name}</strong>
            <span>{person.role}</span>
          </div>
          <div className="staff-dept">{person.department}</div>
          <span className={`duty-status ${person.status === 'Treating patients' ? 'treating' : ''}`}>{person.status}</span>
        </div>
      ))}
    </div>
  )
}
