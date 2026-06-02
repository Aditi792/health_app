from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, date
import re, os, requests

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
CORS(app)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'patients.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# ─────────────────────────────────────
#  Model
# ─────────────────────────────────────
class Patient(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    full_name     = db.Column(db.String(120), nullable=False)
    date_of_birth = db.Column(db.String(20),  nullable=False)
    email         = db.Column(db.String(120), nullable=False, unique=True)
    glucose       = db.Column(db.Float, nullable=False)
    haemoglobin   = db.Column(db.Float, nullable=False)
    cholesterol   = db.Column(db.Float, nullable=False)
    remarks       = db.Column(db.Text, default='')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':            self.id,
            'full_name':     self.full_name,
            'date_of_birth': self.date_of_birth,
            'email':         self.email,
            'glucose':       self.glucose,
            'haemoglobin':   self.haemoglobin,
            'cholesterol':   self.cholesterol,
            'remarks':       self.remarks,
            'created_at':    self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at':    self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
        }


# ─────────────────────────────────────
#  Validation
# ─────────────────────────────────────
def validate_email(email):
    return bool(re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email))

def validate_dob(dob_str):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        if dob >= date.today():
            return False, 'Date of birth cannot be today or a future date.'
        if dob.year < 1900:
            return False, 'Date of birth is too far in the past.'
        return True, ''
    except ValueError:
        return False, 'Invalid date format. Use YYYY-MM-DD.'

def validate_numeric(value, field_name, min_val, max_val):
    try:
        val = float(value)
        if val < min_val or val > max_val:
            return False, f'{field_name} must be between {min_val} and {max_val}.'
        return True, val
    except (TypeError, ValueError):
        return False, f'{field_name} must be a numeric value.'

def validate_patient_data(data):
    errors = []
    if not data.get('full_name', '').strip():
        errors.append('Full name is required.')
    dob = data.get('date_of_birth', '')
    if not dob:
        errors.append('Date of birth is required.')
    else:
        ok, msg = validate_dob(dob)
        if not ok:
            errors.append(msg)
    email = data.get('email', '')
    if not email:
        errors.append('Email address is required.')
    elif not validate_email(email):
        errors.append('Invalid email address format.')
    for field, lo, hi in [('glucose',0,600),('haemoglobin',0,25),('cholesterol',0,700)]:
        ok, result = validate_numeric(data.get(field), field.capitalize(), lo, hi)
        if not ok:
            errors.append(result)
    return errors


# ─────────────────────────────────────
#  Helper
# ─────────────────────────────────────
def calculate_age(dob_str):
    try:
        dob   = datetime.strptime(dob_str, '%Y-%m-%d').date()
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return 30


# ─────────────────────────────────────
#  Rule-based fallback
#  (used when no API key is set)
# ─────────────────────────────────────
def rule_based_prediction(glucose, haemoglobin, cholesterol):
    findings, risks, score = [], [], 0

    if glucose < 70:
        findings.append(f'glucose is low at {glucose} mg/dL — hypoglycaemia risk')
        risks.append('hypoglycaemia'); score += 2
    elif glucose <= 99:
        findings.append(f'glucose is normal at {glucose} mg/dL')
    elif glucose <= 125:
        findings.append(f'glucose is elevated at {glucose} mg/dL — pre-diabetic range')
        risks.append('pre-diabetes'); score += 2
    else:
        findings.append(f'glucose is high at {glucose} mg/dL — diabetic range')
        risks.append('diabetes'); score += 3

    if haemoglobin < 8:
        findings.append(f'haemoglobin critically low at {haemoglobin} g/dL — severe anaemia')
        risks.append('severe anaemia'); score += 3
    elif haemoglobin < 12:
        findings.append(f'haemoglobin low at {haemoglobin} g/dL — anaemia likely')
        risks.append('anaemia'); score += 2
    elif haemoglobin <= 17.5:
        findings.append(f'haemoglobin normal at {haemoglobin} g/dL')
    else:
        findings.append(f'haemoglobin elevated at {haemoglobin} g/dL')
        risks.append('polycythaemia'); score += 1

    if cholesterol < 200:
        findings.append(f'cholesterol desirable at {cholesterol} mg/dL')
    elif cholesterol < 240:
        findings.append(f'cholesterol borderline-high at {cholesterol} mg/dL')
        risks.append('borderline cardiovascular risk'); score += 1
    else:
        findings.append(f'cholesterol high at {cholesterol} mg/dL')
        risks.append('cardiovascular disease risk'); score += 2

    label = {0:'All values within normal range.',
             1:'Mild concern — routine monitoring advised.',
             2:'Mild concern — routine monitoring advised.',
             3:'Moderate concerns — medical review recommended.',
             4:'Moderate concerns — medical review recommended.'}.get(
             score, 'Significant abnormalities — prompt medical attention advised.')

    remark = label + ' Findings: ' + '; '.join(findings) + '.'
    if risks:
        remark += ' Possible conditions to discuss with a doctor: ' + ', '.join(risks) + '.'
    remark += ' This is an automated screening summary — not a medical diagnosis.'
    return remark


# ─────────────────────────────────────
#  Google Gemini API  (FREE — no credit card)
#  Get key: https://aistudio.google.com
#  Set env:  set GEMINI_API_KEY=AIzaSy...
# ─────────────────────────────────────
def gemini_prediction(patient_data):
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return None   # fall through to rule-based

    age = calculate_age(patient_data['date_of_birth'])

    prompt = (
        f"You are a medical screening assistant. A patient has submitted the following blood test results. "
        f"Write a clear, concise health risk assessment in 3-4 sentences. "
        f"Mention which values are outside normal ranges, what conditions they may suggest, "
        f"and whether the patient should see a doctor. Do not give a definitive diagnosis.\n\n"
        f"Patient age: {age} years\n"
        f"Glucose:     {patient_data['glucose']} mg/dL  (Normal fasting: 70-99)\n"
        f"Haemoglobin: {patient_data['haemoglobin']} g/dL  (Normal: 12-17.5)\n"
        f"Cholesterol: {patient_data['cholesterol']} mg/dL  (Desirable: <200, High: >=240)\n\n"
        f"Health assessment:"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 250, "temperature": 0.3}
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            text = (data.get('candidates', [{}])[0]
                       .get('content', {})
                       .get('parts', [{}])[0]
                       .get('text', ''))
            if text.strip():
                return text.strip()
        else:
            print(f"[Gemini] Error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Gemini] Exception: {e}")

    return None   # fall through to rule-based


# ─────────────────────────────────────
#  Master prediction — tries Gemini first,
#  falls back to rule-based engine
# ─────────────────────────────────────
def get_prediction(patient_data):
    result = gemini_prediction(patient_data)
    if result:
        return result
    # Fallback — works with NO API key
    return rule_based_prediction(
        float(patient_data['glucose']),
        float(patient_data['haemoglobin']),
        float(patient_data['cholesterol'])
    )


# ─────────────────────────────────────
#  Routes
# ─────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/patients', methods=['GET'])
def get_patients():
    return jsonify([p.to_dict() for p in Patient.query.order_by(Patient.created_at.desc()).all()])

@app.route('/api/patients/<int:pid>', methods=['GET'])
def get_patient(pid):
    return jsonify(Patient.query.get_or_404(pid).to_dict())

@app.route('/api/patients', methods=['POST'])
def create_patient():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400
    errors = validate_patient_data(data)
    if errors:
        return jsonify({'errors': errors}), 422
    if Patient.query.filter_by(email=data['email'].strip().lower()).first():
        return jsonify({'errors': ['A patient with this email already exists.']}), 409
    p = Patient(
        full_name=data['full_name'].strip(),
        date_of_birth=data['date_of_birth'],
        email=data['email'].strip().lower(),
        glucose=float(data['glucose']),
        haemoglobin=float(data['haemoglobin']),
        cholesterol=float(data['cholesterol']),
        remarks=get_prediction(data),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201

@app.route('/api/patients/<int:pid>', methods=['PUT'])
def update_patient(pid):
    patient = Patient.query.get_or_404(pid)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400
    errors = validate_patient_data(data)
    if errors:
        return jsonify({'errors': errors}), 422
    existing = Patient.query.filter_by(email=data['email'].strip().lower()).first()
    if existing and existing.id != pid:
        return jsonify({'errors': ['Another patient with this email already exists.']}), 409
    patient.full_name     = data['full_name'].strip()
    patient.date_of_birth = data['date_of_birth']
    patient.email         = data['email'].strip().lower()
    patient.glucose       = float(data['glucose'])
    patient.haemoglobin   = float(data['haemoglobin'])
    patient.cholesterol   = float(data['cholesterol'])
    patient.updated_at    = datetime.utcnow()
    patient.remarks       = get_prediction(data)
    db.session.commit()
    return jsonify(patient.to_dict())

@app.route('/api/patients/<int:pid>', methods=['DELETE'])
def delete_patient(pid):
    patient = Patient.query.get_or_404(pid)
    name = patient.full_name
    db.session.delete(patient)
    db.session.commit()
    return jsonify({'message': f'Patient {name} deleted successfully.'})

@app.route('/api/health', methods=['GET'])
def health_check():
    gemini = 'connected' if os.environ.get('GEMINI_API_KEY') else 'not set — using rule-based fallback'
    return jsonify({'status': 'ok', 'patients': Patient.query.count(), 'gemini_api': gemini})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
