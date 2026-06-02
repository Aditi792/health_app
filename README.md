# HealthPredict — Patient Health Prediction App

A full-stack web application for managing patient blood test records with AI-powered health risk prediction.

## Tech Stack

- **Backend**: Python 3.11, Flask, SQLAlchemy (SQLite)
- **Frontend**: Vanilla HTML/CSS/JavaScript (no framework dependencies)
- **AI/ML**: Gemini API (falls back to rule-based engine if no key)
- **Database**: SQLite (via SQLAlchemy ORM)

## Features

- Full CRUD for patient records
- Blood test input: Glucose, Haemoglobin, Cholesterol
- AI-generated health remarks via GEMINI API (gemini-2.0-flash)
- Rule-based fallback predictor (no API key required for demo)
- Colour-coded value badges (normal / borderline / high)
- Live search, CSV export
- Input validation (frontend + backend)
- Responsive layout

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/Aditi792/health_app.git
cd health_app

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Set your GEMINI API key (optional — app works without it)
export GEMINI_API_KEY=your_key_here   # Windows: set GEMINI_API_KEY=your_key_here

# 5. Run the application
python backend/app.py
```

Then open **http://localhost:5000** in your browser.

## Project Structure

```
health_app/
├── backend/
│   ├── app.py              # Flask app, API routes, DB models, AI integration
│   ├── requirements.txt
│   └── patients.db         # SQLite database (auto-created on first run)
├── frontend/
│   ├── templates/
│   │   └── index.html      # Main SPA template
│   └── static/
│       ├── css/style.css
│       └── js/app.js
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patients` | List all patients |
| GET | `/api/patients/:id` | Get single patient |
| POST | `/api/patients` | Create patient + generate remarks |
| PUT | `/api/patients/:id` | Update patient + regenerate remarks |
| DELETE | `/api/patients/:id` | Delete patient |
| GET | `/api/health` | Health check |

## AI Prediction Logic

1. **With GEMINI_API_KEY set**: sends patient vitals to `gemini-2.0-flash` with a medical prompt and returns a concise 2–3 sentence health risk assessment.
2. **Without API key**: falls back to a deterministic rule-based engine that classifies each blood value against standard clinical reference ranges and produces a structured remarks string.

## Normal Reference Ranges Used

| Marker | Low | Normal | High |
|--------|-----|--------|------|
| Glucose | <70 mg/dL | 70–99 | ≥126 |
| Haemoglobin | <12 g/dL | 12–17.5 | >17.5 |
| Cholesterol | — | <200 mg/dL | ≥240 |

## Security Notes

- All API keys are read from environment variables — never hardcoded
- Input sanitised on both client and server
- Email uniqueness enforced at the database level
- No sensitive data in version control (`.gitignore` covers `.env`, `*.db`)
