# GramArogya AI — Frontend

Single React + Vite application serving **both** the hospital admin portal
(`/admin/*`) and the patient/public interface (`/patient/*`) via role-based
layouts — not two separate codebases.

## Status

The Vite application is scaffolded in **Phase 2 (Set Up Development
Environments)**. The `src/` folders below mark the intended structure ahead of
that step:

```
src/
├── main.jsx
├── App.jsx
├── api.js                 # all requests to the FastAPI backend
├── components/            # Layout, MetricCard, ForecastChart, DataTable, ProtectedRoute
├── pages/
│   ├── LoginPage.jsx
│   ├── admin/             # Dashboard, Forecast, ResourcePlan, Workforce, Emergency, Fairness
│   └── patient/           # PatientHome, FacilitySearch, FacilityDetails, PatientEmergency
└── styles/app.css
```

## Setup (Phase 2)

```bash
conda activate gramarogya      # provides Node.js 22 + npm
cd frontend
npm create vite@latest . -- --template react
npm install
npm run dev                    # http://localhost:5173
```
