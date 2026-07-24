<!-- The YAML block below configures the Hugging Face Space. GitHub renders it as
     a small metadata table; it is required by HF and harmless everywhere else. -->
---
title: GramArogya AI
emoji: 🏥
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# GramArogya AI

> **An AI-powered rural healthcare operations and patient-access prototype for demand forecasting, fair workforce scheduling, resource planning, emergency coordination, and facility guidance.**

---

## 1. Project Overview

**GramArogya AI** is a decision-support prototype designed for a selected rural hospital in **Gadchiroli district, Maharashtra**.

Rural patients often travel long distances without knowing whether the required doctor, nurse, medicine, bed, diagnostic facility, or emergency support is available. At the same time, rural hospitals face fluctuating patient demand, limited staff availability, workforce fatigue, medicine shortages, bed constraints, and sudden emergency surges.

This project connects hospital operations and patient access through one integrated platform:

- Predict future patient demand
- Plan required staff, beds, medicines, and equipment
- Generate a fair and skill-aware staff roster
- Detect likely capacity overload
- Coordinate emergency support with nearby capable facilities
- Help patients identify an appropriate available healthcare facility

The prototype supports two user experiences:

1. **Hospital Administration Web Dashboard**
2. **Patient-Facing Mobile-Responsive Interface**

---

## 2. Problem Statement

A rural hospital may have limited doctors, nurses, technicians, beds, medicines, and emergency resources. Patient demand changes because of:

- Seasonal disease patterns
- Rainfall and weather
- Festivals and local events
- Weekly market days
- Vaccination or health camps
- Disease outbreaks
- Accidents and mass-casualty situations
- Staff leave and unplanned absence

Traditional planning is often manual and reactive. As a result:

- Workers may be assigned unfair or exhausting shifts
- Required skills may not be available during a shift
- Medicines and equipment may not be prepared before a surge
- Beds may become unavailable without advance warning
- Patients may travel to an unsuitable or unavailable facility
- Nearby hospitals may be informed only after the primary hospital becomes overloaded

**GramArogya AI aims to make rural healthcare planning predictive, coordinated, explainable, and human-controlled.**

---

## 3. Project Objectives

The prototype is designed to:

1. Forecast patient arrivals for the next **1–7 days**
2. Forecast demand by service category:
   - General OPD
   - Fever and infectious cases
   - Maternal and child care
   - Trauma and emergency
3. Convert predicted demand into resource requirements
4. Generate designation-, skill-, leave-, fatigue-, and fairness-aware staff rosters
5. Detect shortages in:
   - Workforce
   - Beds
   - Medicines
   - Equipment
   - Ambulance capacity
6. Trigger emergency-readiness workflows when predicted demand exceeds capacity
7. Rank nearby facilities using capability and road travel time
8. Provide patients with availability-based facility guidance without diagnosing disease

---

## 4. Target Users

### Primary User: Hospital Administrator

The hospital administrator, roster manager, or operations officer uses the web dashboard to:

- Review demand forecasts
- Generate and approve staff schedules
- Check workforce shortages
- Plan beds, medicines, and equipment
- Monitor fairness and fatigue indicators
- Simulate emergency scenarios
- Alert nearby facilities
- Review audit logs and manual overrides

### Secondary User: Rural Patient or Caregiver

The patient interface helps users:

- Find a nearby capable healthcare facility
- Check whether a required service is available
- View estimated waiting time
- Check emergency or bed availability
- Call the hospital or ambulance
- Receive outbreak-related guidance
- Use Marathi, Hindi, or English
- Access essential information without mandatory registration

The patient interface **does not diagnose disease**. It only provides facility guidance and emergency contact support.

---

## 5. Case-Study Scope

The prototype focuses on:

- **One primary rural hospital**
- A selected rural region in **Gadchiroli district**
- Nearby PHCs, CHCs, rural hospitals, and referral facilities
- A road-travel-time-based emergency support network

The primary hospital runs the complete forecasting and planning workflow. Nearby facilities mainly provide:

- Referral capacity
- Emergency beds
- Specialist support
- Ambulance support
- Oxygen or equipment support
- Temporary overflow assistance

The design can later be scaled to multiple hospitals.

---

## 6. Core System Workflow

```mermaid
flowchart TD
    A[Historical Patient, Weather, Event and Outbreak Data] --> B[Demand Forecasting]
    B --> C[1 to 7 Day Patient Forecast]
    C --> D[Resource Planning]
    D --> E[Required Staff, Beds, Medicines and Equipment]
    E --> F[Workforce Optimization using NSGA-II]
    F --> G[Recommended Staff Roster]
    C --> H[Capacity and Emergency Check]
    D --> H
    H -->|Capacity sufficient| I[Normal Operations Plan]
    H -->|Predicted overload| J[Emergency Coordination Engine]
    J --> K[Rank Nearby Capable Facilities]
    K --> L[Send and Track Alerts]
    I --> M[Hospital Admin Dashboard]
    G --> M
    L --> M
    M --> N[Approved Availability Data]
    N --> O[Patient Interface]
```

---

## 7. System Architecture

```mermaid
flowchart LR
    subgraph Data["Data Sources"]
        D1[Demand and Resource CSV]
        D2[Staff Master CSV]
        D3[PostgreSQL Operational Data]
        D4[Weather, Events and Outbreak Inputs]
    end

    subgraph Backend["FastAPI Backend"]
        B1[Authentication and Role Control]
        B2[Forecasting Service]
        B3[Resource Planning Service]
        B4[Workforce Optimization Service]
        B5[Emergency Coordination Service]
        B6[Patient Routing Service]
        B7[Planning Orchestrator]
    end

    subgraph Storage["Storage"]
        S1[(PostgreSQL)]
        S2[Saved ML Model and Metrics]
    end

    subgraph Frontend["React Frontend"]
        F1[Hospital Admin Portal]
        F2[Patient Interface]
    end

    D1 --> B7
    D2 --> B7
    D3 --> B7
    D4 --> B2

    B7 --> B2
    B2 --> B3
    B3 --> B4
    B2 --> B5
    B3 --> B5
    B5 --> B6

    B1 --> S1
    B2 --> S2
    B2 --> S1
    B3 --> S1
    B4 --> S1
    B5 --> S1
    B6 --> S1

    S1 --> F1
    S1 --> F2
```

---

## 8. Main Modules and Methods

| Module | Purpose | Method or Algorithm |
|---|---|---|
| Demand Forecasting | Predict patient arrivals for the next 1–7 days | XGBoost as primary model; Random Forest and seasonal-naive models for comparison |
| Feature Engineering | Capture time, season, events, weather, outbreaks, and recent demand | Calendar variables, lag features, rolling averages, categorical encoding |
| Resource Planning | Convert predicted patient categories into operational requirements | Explainable formulas, capacity rules, safety stock, reorder-point logic |
| Workforce Optimization | Generate a valid and fair roster | NSGA-II multi-objective evolutionary optimization |
| Emergency Detection | Determine whether the hospital may be overloaded | Forecast plus explainable threshold and capacity rules |
| Emergency Coordination | Rank and alert nearby capable facilities | Capability filtering and road-travel-time ranking |
| Patient Routing | Recommend a suitable available facility | Rule-based ranking using service availability, distance, waiting time, and capacity |
| Authentication | Separate administrator and patient experiences | Role-based access control and patient guest access or OTP |

---

## 9. Why NSGA-II Is Used

A basic Genetic Algorithm can search for a good staff roster, but hospitals have several competing goals:

- Maintain minimum service coverage
- Assign staff with the correct skills and designation
- Minimize overtime
- Minimize fatigue
- Balance night and weekend shifts
- Respect leave and availability
- Improve preference satisfaction
- Reduce understaffing

There is rarely one roster that is best for every objective.

**NSGA-II** generates a group of strong trade-off schedules instead of forcing all objectives into one unclear score.

The administrator may receive options such as:

- **Option A:** Highest patient-service coverage
- **Option B:** Highest workforce fairness
- **Option C:** Balanced recommended roster

The final schedule remains subject to human review and approval.

---

## 10. Dataset Design

Only two source CSV files are maintained inside the project.

### 10.1 `demand_resource_daily.csv`

This file contains historical daily demand and resource information.

Historical period:

- **1 January 2020 to 31 December 2025**

The first demonstration forecast begins on:

- **1 January 2026**

Main demand-forecasting columns include:

- Date
- Day of week
- Month and season
- Weekend and holiday flags
- Festival or local-event indicators
- Weekly market day
- Vaccination or maternal-clinic day
- Rainfall
- Temperature
- Humidity
- Outbreak type and severity
- Historical patient counts
- Lag features
- Rolling averages
- Patient-category targets

Main target columns include:

- `total_patient_arrivals`
- `general_opd_arrivals`
- `fever_infectious_arrivals`
- `maternal_child_arrivals`
- `trauma_emergency_arrivals`
- `expected_admissions`

The same file can also contain current resource status and explainable planning outputs, such as:

- Available beds
- Medicine stock
- Equipment availability
- Calculated resource requirements
- Emergency risk level

**Important:** Resource requirement outputs are not used as demand-model predictors because that would create target leakage.

### 10.2 `staff_master.csv`

This file stores the workforce information needed by NSGA-II.

Main columns include:

- Staff ID
- Staff category
- Designation
- Department
- Qualification
- Experience
- Skill tags
- Shift eligibility
- Maximum weekly hours
- Minimum rest hours
- Maximum consecutive working days
- Night-shift limit
- Preferred shift
- Emergency on-call eligibility
- Employment type
- Active status

Examples of roles include:

- Medical Superintendent
- General Medical Officer
- Emergency Medical Officer
- Physician
- Pediatrician
- Obstetrician and Gynecologist
- Nursing Superintendent
- Assistant Nursing Superintendent
- Senior Nursing Officer
- Nursing Officer
- Auxiliary Nurse Midwife
- Pharmacist
- Laboratory Technician
- Radiographer
- Ambulance EMT and Driver

---

## 11. Demand Forecasting Process

```mermaid
flowchart LR
    A[2020 to 2025 Historical Data] --> B[Data Validation]
    B --> C[Feature Engineering]
    C --> D[Chronological Train Validation Test Split]
    D --> E1[XGBoost]
    D --> E2[Random Forest]
    D --> E3[Seasonal Naive Baseline]
    E1 --> F[Evaluate R2 MAE RMSE WAPE]
    E2 --> F
    E3 --> F
    F --> G[Select Best Generalizing Model]
    G --> H[Save Model]
    H --> I[Forecast 1 to 7 January 2026]
```

The model is evaluated using a chronological split rather than a random split because future observations must remain unseen during training.

Evaluation metrics:

- R²
- Mean Absolute Error
- Root Mean Squared Error
- Weighted Absolute Percentage Error
- Horizon-wise error from Day 1 to Day 7

A high R² is useful, but the selected model must also:

- Beat simple forecasting baselines
- Avoid data leakage
- Perform consistently on unseen dates
- Produce operationally useful category-level forecasts

---

## 12. Resource Planning Logic

Resource planning uses the forecast output rather than a separate demand model.

```text
Predicted patient demand
        +
Patient category
        +
Current resource availability
        +
Operational planning rules
        =
Required staff, beds, medicines and equipment
```

Examples:

- Fever surge → physician, nurse, lab, test-kit, PPE, IV-fluid, and isolation-bed requirements
- Maternal-child demand → pediatrician, obstetrician, ANM, nursing, and maternal-bed requirements
- Trauma surge → emergency doctor, senior nurse, ambulance, oxygen, and emergency-bed requirements

Resource planning includes:

- Workforce demand calculation
- Bed allocation
- Medicine planning
- Equipment planning
- Ambulance planning
- Shortage detection
- Surplus detection
- Safety stock and reorder alerts

---

## 13. Emergency Scenario Workflow

The emergency component uses both machine learning and rules.

### Prediction Stage

The demand model estimates the number and category of patients likely to arrive.

### Decision Stage

The system compares predicted requirements with available capacity.

Example:

```text
If predicted emergency demand exceeds safe capacity:
    Create emergency planning run
    Calculate expected overflow
    Identify required support
    Rank nearby facilities
    Prepare alert
    Request administrator approval
    Send alert
    Track acknowledgement
```

Supported prototype scenarios may include:

- Dengue or fever surge
- Malaria surge
- Acute diarrhoeal disease
- Respiratory outbreak
- Festival-related surge
- Road accident or mass-casualty event

Each scenario affects resources differently.

---

## 14. API Coordination

Frontend pages do not directly send data to each other. They communicate with the FastAPI backend.

A shared `planning_run_id` connects the outputs of one complete planning cycle.

```mermaid
sequenceDiagram
    participant Admin as Admin Dashboard
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Forecast as Forecast Service
    participant Resource as Resource Planner
    participant Roster as NSGA-II Service
    participant Emergency as Emergency Engine

    Admin->>API: Start planning run
    API->>DB: Create planning_run_id
    API->>Forecast: Generate 1-7 day forecast
    Forecast->>DB: Save forecast
    API->>Resource: Calculate resource requirements
    Resource->>DB: Save resource plan
    API->>Roster: Generate roster options
    Roster->>DB: Save schedule options
    API->>Emergency: Check capacity and risk
    Emergency->>DB: Save alerts and recommendations
    API-->>Admin: Return combined dashboard response
```

Example API endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/admin/login` | Hospital administrator login |
| `POST /api/planning-runs` | Start a complete planning workflow |
| `GET /api/dashboard/summary` | Retrieve combined dashboard information |
| `POST /api/forecast/run` | Generate a 1–7 day patient forecast |
| `GET /api/forecast/latest` | Retrieve the latest saved forecast |
| `POST /api/resources/plan` | Calculate required operational resources |
| `POST /api/workforce/generate` | Generate NSGA-II roster options |
| `POST /api/emergency/check` | Evaluate overload and emergency conditions |
| `POST /api/emergency/alerts` | Send approved facility alerts |
| `GET /api/patient/facilities` | Rank suitable facilities for patients |
| `GET /api/patient/facilities/{id}` | Retrieve facility details |

---

## 15. User Interfaces

### Hospital Administration Portal

Main pages:

- Login
- Overview Dashboard
- Demand Forecast
- Resource Planning
- Workforce Roster
- Emergency Network
- Fairness and Audit
- Reports

Main analytics:

- Actual versus predicted patients
- Seven-day patient forecast
- Department-wise demand
- Staff coverage heatmap
- Bed occupancy
- Medicine stock risk
- Equipment utilization
- Expected waiting time
- Workforce fairness indicators
- Emergency map
- Nearby facility readiness

### Patient Interface

Main screens:

- Language and accessibility selection
- Find a hospital
- Required service selection
- Facility recommendation
- Facility details
- Emergency help
- Ambulance contact
- Outbreak alert
- Directions and call support

Public pages should avoid showing personal staff details.

---

## 16. Ethical and AI Guardrails

### Workforce Fairness

The roster must:

- Respect qualifications and skill requirements
- Respect approved leave
- Respect maximum working hours
- Maintain minimum rest periods
- Limit consecutive difficult shifts
- Balance night and weekend duties within comparable roles
- Reduce overtime and fatigue
- Record preference satisfaction
- Avoid unfairly overusing the same workers

Fairness does not mean treating every designation as interchangeable. Comparisons must be made between workers with comparable responsibilities and qualifications.

### Human Oversight

- AI recommends; the administrator approves
- Manual overrides require a reason
- All planning decisions are logged
- Administrators can reject or modify a proposed schedule
- Emergency alerts require approval unless an authorized policy permits automatic sending

### Patient Safety

- No disease diagnosis
- No guaranteed bed unless confirmed
- Show the last-updated time of availability information
- Recommend emergency calling when data may be stale
- Do not replace clinical judgement
- Provide clear escalation instructions

### Privacy and Security

- Role-based access control
- Password hashing
- Minimal patient data collection
- Encryption in transit
- No public exposure of staff schedules
- Audit logs
- Environment secrets stored outside Git
- Consent before location sharing

### Accessibility

- Marathi, Hindi, and English
- Low-bandwidth mode
- Large-text mode
- Simple icons and language
- Guest access for basic facility search
- Voice support in later versions

---

## 17. Research Gap and Prototype Contribution

Existing research often addresses one isolated problem:

- Nurse rostering
- Physician scheduling
- Patient demand forecasting
- Bed optimization
- Inventory planning
- Emergency referral
- Rural patient navigation

**GramArogya AI integrates these decisions into one explainable operational workflow.**

The main contribution is not a newly invented algorithm. The contribution is an integrated prototype that:

1. Forecasts patient demand by service category
2. Converts forecasts into operational requirements
3. Generates designation- and skill-aware fair staff rosters
4. Detects overload before the hospital reaches crisis level
5. Coordinates support with nearby capable facilities
6. Shares approved availability information with rural patients
7. Keeps human administrators responsible for final decisions

---

## 18. Technology Stack

### Frontend

- React
- Vite
- JavaScript or TypeScript
- Responsive web design
- Charting library
- Mapping library

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Uvicorn

### Machine Learning and Optimization

- Pandas
- NumPy
- Scikit-learn
- XGBoost
- DEAP or pymoo for NSGA-II
- Joblib

### Database

- PostgreSQL

### Testing

- Pytest
- FastAPI test client
- Frontend component tests
- API integration tests

### Version Control

- Git
- GitHub
- `main` and `develop` branches

---

## 19. Recommended Project Structure

```text
rural-healthcare-ai/
|
|-- README.md
|-- .gitignore
|-- .env.example
|-- requirements.txt
|-- package.json
|
|-- data/
|   |-- demand_resource_daily.csv
|   `-- staff_master.csv
|
|-- backend/
|   |-- __init__.py
|   |-- main.py
|   |-- config.py
|   |-- db.py
|   |-- db_models.py
|   |-- schemas.py
|   |-- routes.py
|   |-- auth.py
|   |-- seed_database.py
|   |
|   |-- services/
|   |   |-- __init__.py
|   |   |-- forecasting.py
|   |   |-- resource_planning.py
|   |   |-- workforce_optimization.py
|   |   |-- emergency.py
|   |   |-- patient_routing.py
|   |   `-- planning_orchestrator.py
|   |
|   `-- artifacts/
|       |-- demand_model.joblib
|       |-- feature_config.json
|       `-- model_metrics.json
|
|-- frontend/
|   |-- package.json
|   |-- vite.config.js
|   |-- index.html
|   `-- src/
|       |-- main.jsx
|       |-- App.jsx
|       |-- api.js
|       |
|       |-- components/
|       |   |-- Layout.jsx
|       |   |-- MetricCard.jsx
|       |   |-- ForecastChart.jsx
|       |   |-- DataTable.jsx
|       |   `-- ProtectedRoute.jsx
|       |
|       |-- pages/
|       |   |-- LoginPage.jsx
|       |   |-- admin/
|       |   |   |-- DashboardPage.jsx
|       |   |   |-- ForecastPage.jsx
|       |   |   |-- ResourcePlanPage.jsx
|       |   |   |-- WorkforcePage.jsx
|       |   |   |-- EmergencyPage.jsx
|       |   |   `-- FairnessPage.jsx
|       |   `-- patient/
|       |       |-- PatientHomePage.jsx
|       |       |-- FacilitySearchPage.jsx
|       |       |-- FacilityDetailsPage.jsx
|       |       `-- PatientEmergencyPage.jsx
|       |
|       `-- styles/
|           `-- app.css
|
|-- scripts/
|   |-- validate_data.py
|   |-- train_forecast_model.py
|   `-- generate_demo_forecast.py
|
`-- tests/
    |-- test_forecasting.py
    |-- test_resource_planning.py
    |-- test_workforce_optimization.py
    |-- test_emergency.py
    `-- test_api.py
```

---

## 20. Local Development Setup

### 20.1 Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd rural-healthcare-ai
```

### 20.2 Create the Python Environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

### 20.3 Configure Environment Variables

Copy the example file:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Example variables:

```env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/gramarogya
SECRET_KEY=replace_with_a_secure_secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:5173
```

Never commit `.env`.

### 20.4 Create the PostgreSQL Database

```sql
CREATE DATABASE gramarogya;
```

### 20.5 Validate and Import Data

```bash
python scripts/validate_data.py
python -m backend.seed_database
```

### 20.6 Train the Forecasting Model

```bash
python scripts/train_forecast_model.py
```

Expected saved artifacts:

```text
backend/artifacts/demand_model.joblib
backend/artifacts/feature_config.json
backend/artifacts/model_metrics.json
```

### 20.7 Run the FastAPI Backend

```bash
uvicorn backend.main:app --reload
```

Backend URL:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

### 20.8 Run the React Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

---

## 21. Typical Application Run

1. Administrator logs in.
2. The system retrieves the latest hospital and staff data.
3. Administrator starts a planning run.
4. The forecasting service generates a seven-day forecast.
5. The resource planner calculates requirements.
6. NSGA-II generates roster options.
7. The emergency engine checks projected capacity.
8. The dashboard displays:
   - Forecast
   - Resource shortages
   - Staff schedules
   - Fairness indicators
   - Emergency risk
9. Administrator reviews and approves recommendations.
10. Approved availability information becomes visible to the patient interface.
11. If an emergency alert is approved, nearby facilities receive the request and their response is tracked.

---

## 22. Git and GitHub Setup

```bash
git init
git add .
git commit -m "Initialize GramArogya AI prototype"
git branch -M main
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main

git checkout -b develop
git push -u origin develop
```

Recommended workflow:

- `main` contains stable demonstration code
- `develop` contains integrated development work
- Feature branches are created from `develop`
- Pull requests are reviewed before merging

Examples:

```bash
git checkout -b feature/demand-forecasting
git checkout -b feature/workforce-optimization
git checkout -b feature/admin-dashboard
git checkout -b feature/patient-interface
```

---

## 23. Current Prototype Status

At the current stage:

- Project scope has been defined
- Target users have been identified
- Architecture and workflow have been designed
- Synthetic historical data has been prepared
- A seven-day demonstration forecast has been generated
- Workforce roles and designations have been defined
- Resource-planning logic has been designed
- UI concepts have been prepared
- The implementation roadmap and folder structure are available

Remaining implementation work includes:

- Consolidating the final two source CSV files
- Creating PostgreSQL tables
- Implementing and saving the forecasting pipeline
- Implementing NSGA-II roster generation
- Building FastAPI endpoints
- Building the admin and patient interfaces
- Adding emergency-facility data
- Adding testing, deployment, and final evaluation

---

## 24. Prototype Limitations

- The initial dataset is synthetic and must not be treated as real clinical evidence
- Patient routing depends on accurate and frequently updated facility information
- Road and ambulance conditions may change rapidly
- Emergency scenarios are simplified simulations
- The system does not provide diagnosis or treatment
- Resource formulas require validation by healthcare professionals
- Staff rules require validation against applicable employment and health-service policies
- The Gadchiroli case-study facility and referral network must be finalized using verified local information

---

## 25. Future Enhancements

- Real HMIS and hospital information-system integration
- Live weather and outbreak-surveillance feeds
- GPS and road-condition-aware travel estimates
- SMS and IVR support for low-connectivity regions
- ASHA-worker interface
- Ambulance dispatch integration
- Real-time schedule repair after absence
- Explainable forecast drivers
- Patient appointment and referral tracking
- Multi-hospital optimization
- Federated or privacy-preserving learning
- Clinician-validated symptom and service routing
- Mobile application using React Native or Flutter

---

## 26. Disclaimer

GramArogya AI is an academic decision-support prototype. It is not a certified medical device, diagnostic system, emergency-response authority, or replacement for healthcare professionals.

All recommendations must be reviewed by authorized hospital personnel before operational use.
