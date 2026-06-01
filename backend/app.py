from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import re
import os
import requests

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
CORS(app)

# --- Database config ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'patients.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- Model ---
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    date_of_birth = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    glucose = db.Column(db.Float, nullable=False)
    haemoglobin = db.Column(db.Float, nullable=False)
    cholesterol = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth,
            'email': self.email,
            'glucose': self.glucose,
            'haemoglobin': self.haemoglobin,
            'cholesterol': self.cholesterol,
            'remarks': self.remarks,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
        }


# --- Validation helpers ---
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_dob(dob_str):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        if dob >= date.today():
            return False, 'Date of birth cannot be today or a future date.'
        if dob.year < 1900:
            return False, 'Date of birth seems unrealistically old.'
        return True, ''
    except ValueError:
        return False, 'Invalid date format. Use YYYY-MM-DD.'


def validate_numeric(value, field_name, min_val=0, max_val=9999):
    try:
        val = float(value)
        if val < min_val or val > max_val:
            return False, f'{field_name} must be between {min_val} and {max_val}.'
        return True, val
    except (TypeError, ValueError):
        return False, f'{field_name} must be a numeric value.'


def validate_patient_data(data, is_update=False):
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

    for field, min_v, max_v in [('glucose', 0, 600), ('haemoglobin', 0, 25), ('cholesterol', 0, 700)]:
        ok, result = validate_numeric(data.get(field), field.capitalize(), min_v, max_v)
        if not ok:
            errors.append(result)

    return errors


# --- AI/ML prediction via Claude (Anthropic API) ---
def get_ai_prediction(patient_data):
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return generate_rule_based_prediction(patient_data)

    prompt = f"""You are a medical AI assistant. Based on the following blood test results, provide a concise health risk assessment (2-3 sentences). Be factual and mention any values outside normal ranges. Do not provide definitive diagnoses.

Patient: {patient_data['full_name']}, Age: {calculate_age(patient_data['date_of_birth'])} years
- Glucose: {patient_data['glucose']} mg/dL (Normal: 70-99 mg/dL fasting)
- Haemoglobin: {patient_data['haemoglobin']} g/dL (Normal: Men 13.5-17.5, Women 12-15.5)
- Cholesterol: {patient_data['cholesterol']} mg/dL (Desirable: <200, Borderline: 200-239, High: >=240)

Provide a brief health remark:"""

    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 200,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            return data['content'][0]['text'].strip()
    except Exception:
        pass

    return generate_rule_based_prediction(patient_data)


def calculate_age(dob_str):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return 'Unknown'


def generate_rule_based_prediction(data):
    glucose = float(data['glucose'])
    haemoglobin = float(data['haemoglobin'])
    cholesterol = float(data['cholesterol'])
    findings = []
    risks = []

    # Glucose assessment
    if glucose < 70:
        findings.append('glucose is low (hypoglycaemia risk)')
        risks.append('hypoglycaemia')
    elif 100 <= glucose <= 125:
        findings.append('glucose is in the pre-diabetic range')
        risks.append('pre-diabetes')
    elif glucose >= 126:
        findings.append('glucose is elevated (possible diabetes)')
        risks.append('diabetes')
    else:
        findings.append('glucose is within normal range')

    # Haemoglobin assessment
    if haemoglobin < 12.0:
        findings.append('haemoglobin is low (anaemia likely)')
        risks.append('anaemia')
    elif haemoglobin > 17.5:
        findings.append('haemoglobin is elevated')
        risks.append('polycythaemia')
    else:
        findings.append('haemoglobin is within normal range')

    # Cholesterol assessment
    if cholesterol >= 240:
        findings.append('cholesterol is high (cardiovascular risk)')
        risks.append('cardiovascular disease')
    elif cholesterol >= 200:
        findings.append('cholesterol is borderline high')
        risks.append('borderline cardiovascular risk')
    else:
        findings.append('cholesterol is at a desirable level')

    summary = f"Blood results show: {'; '.join(findings)}. "
    if risks:
        summary += f"Potential health risks include: {', '.join(risks)}. "
        summary += "Follow-up with a healthcare professional is recommended."
    else:
        summary += "All values appear within acceptable ranges. Routine monitoring is advised."

    return summary


# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/patients', methods=['GET'])
def get_patients():
    patients = Patient.query.order_by(Patient.created_at.desc()).all()
    return jsonify([p.to_dict() for p in patients])


@app.route('/api/patients/<int:patient_id>', methods=['GET'])
def get_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return jsonify(patient.to_dict())


@app.route('/api/patients', methods=['POST'])
def create_patient():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400

    errors = validate_patient_data(data)
    if errors:
        return jsonify({'errors': errors}), 422

    # Check duplicate email
    if Patient.query.filter_by(email=data['email'].strip().lower()).first():
        return jsonify({'errors': ['A patient with this email already exists.']}), 409

    # Get AI prediction
    remarks = get_ai_prediction(data)

    patient = Patient(
        full_name=data['full_name'].strip(),
        date_of_birth=data['date_of_birth'],
        email=data['email'].strip().lower(),
        glucose=float(data['glucose']),
        haemoglobin=float(data['haemoglobin']),
        cholesterol=float(data['cholesterol']),
        remarks=remarks,
    )
    db.session.add(patient)
    db.session.commit()
    return jsonify(patient.to_dict()), 201


@app.route('/api/patients/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400

    errors = validate_patient_data(data, is_update=True)
    if errors:
        return jsonify({'errors': errors}), 422

    # Check duplicate email (excluding current patient)
    existing = Patient.query.filter_by(email=data['email'].strip().lower()).first()
    if existing and existing.id != patient_id:
        return jsonify({'errors': ['Another patient with this email already exists.']}), 409

    patient.full_name = data['full_name'].strip()
    patient.date_of_birth = data['date_of_birth']
    patient.email = data['email'].strip().lower()
    patient.glucose = float(data['glucose'])
    patient.haemoglobin = float(data['haemoglobin'])
    patient.cholesterol = float(data['cholesterol'])
    patient.updated_at = datetime.utcnow()

    # Regenerate remarks if blood values changed
    patient.remarks = get_ai_prediction(data)

    db.session.commit()
    return jsonify(patient.to_dict())


@app.route('/api/patients/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    db.session.delete(patient)
    db.session.commit()
    return jsonify({'message': f'Patient {patient.full_name} deleted successfully.'})


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'patients': Patient.query.count()})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
