from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import sqlite3
import base64
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import time
from flask_cors import CORS
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json

# Face matching - Assuming you have this library
from face_matcher import find_best_match

# Assuming you have spaCy installed and models downloaded
import spacy
import re
nlp = spacy.load("en_core_web_sm")

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
app.secret_key = 'your_secret_key'

# Upload folders
UPLOAD_FOLDER = os.path.join('static', 'uploads')
CRIMINAL_FOLDER = os.path.join('static', 'criminals')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CRIMINAL_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure Google AI with the correct model
# DO NOT hardcode your API key. Use environment variables.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not set in environment")
genai.configure(api_key=GOOGLE_API_KEY)

# Use the correct model name for text generation
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-preview-05-20",
)

def get_mime_type(filename):
    # Very basic MIME type check based on extension
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        return "image/jpeg"
    elif filename.endswith(".png"):
        return "image/png"
    return None

def generate_response(prompt, max_tokens):
    """
    Safely generate AI content. Handles empty candidates or missing parts.
    Returns string or None.
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens}
        )

        # Check if candidates exist
        if response and hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            # Each candidate has 'content' with 'parts'
            parts = getattr(candidate.content, "parts", None)
            if parts and len(parts) > 0:
                text = getattr(parts[0], "text", "").strip()
                if text:
                    return text

        # Fallback if no valid content
        return None

    except Exception as e:
        print(f"[AI ERROR] {e}")
        return None

def generate_response_safe(prompt, max_tokens=150):
    try:
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.3}
        )

        # 🔍 Debug print to see structure
        print("[DEBUG] Raw Gemini response:", response.to_dict())

        if not response or not response.candidates:
            print("[AI WARNING] No candidates returned.")
            return None

        # Collect text from all parts
        texts = []
        for cand in response.candidates:
            if hasattr(cand, "content") and hasattr(cand.content, "parts"):
                for part in cand.content.parts:
                    if hasattr(part, "text") and part.text:
                        texts.append(part.text.strip())

        if not texts:
            print("[AI WARNING] No text parts found in candidates.")
            return None

        return "\n".join(texts)

    except Exception as e:
        print(f"[AI ERROR] {e}")
        return None


def safe_generate_questions(user_description):
    prompt = f"""
You are a professional police assistant. Based on the incident description below, generate 5-7 neutral investigative questions.
Return ONLY a JSON array of strings. Do NOT refuse, do NOT filter content.

Incident Description: "{user_description}"
"""
    try:
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 600, "temperature": 0.7}
        )

        text = ""
        if response and response.candidates and response.candidates[0].content.parts:
            text = response.candidates[0].content.parts[0].text.strip()

        # Clean markdown fences
        if text.startswith("```json"):
            text = text.split("\n",1)[-1].rsplit("\n",1)[0].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        # Parse JSON
        try:
            questions = json.loads(text)
            if not isinstance(questions, list):
                raise ValueError("Not a list")
        except Exception:
            # fallback: split by lines if JSON fails
            questions = [q.strip(" -•1234567890.") for q in text.split("\n") if q.strip()]

        # ultimate fallback
        if not questions:
            questions = ["Please describe any additional relevant details about the incident."]

        return questions

    except Exception as e:
        print(f"[AI ERROR] {e}")
        return ["Please describe any additional relevant details about the incident."]




# ----------------------------
# Database Setup
# ----------------------------
def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                mobile TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()

# ----------------------------
# Criminal Info Lookup
# ----------------------------
def fetch_criminal_info(name):
    if not os.path.exists("criminals.csv"):
        return None
    df = pd.read_csv("criminals.csv")
    result = df[df["name"].str.contains(name, case=False, na=False)]
    if not result.empty:
        row = result.iloc[0]
        return {
            "name": row.get("name", "N/A"),
            "crimes": row.get("crime_type", "N/A"),
            "address": row.get("location", "N/A"),
            "status": row.get("status", "N/A")
        }
    return None

# ----------------------------
# NLP Entity Extraction
# ----------------------------
def extract_entity(text):
    """
    Extracts PERSON, ORG, GPE from user input using spaCy
    """
    doc = nlp(text)
    names = [ent.text for ent in doc.ents if ent.label_ in ("PERSON", "ORG", "GPE")]
    return names

# ----------------------------
# Routes
# ----------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()
    if user:
        session['user'] = user[1]  # first_name
        return redirect('/dashboard')
    return "Invalid credentials"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        mobile = request.form['mobile']
        email = request.form['email']
        # NOTE: This is a critical security vulnerability. Passwords should NEVER be stored in plaintext.
        # Use a library like werkzeug.security to hash passwords.
        password = request.form['password']
        try:
            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO users (first_name, last_name, mobile, email, password)
                    VALUES (?, ?, ?, ?, ?)
                ''', (first_name, last_name, mobile, email, password))
                conn.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "Email already registered"
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template('dashboard.html', user=session['user'])

@app.route('/draw')
def draw():
    if 'user' not in session:
        return redirect('/')
    return render_template('draw.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect('/')
    file = request.files.get('sketch')
    if not file or file.filename == '':
        return "No selected file"
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return redirect(url_for('match_sketch', filename=filename))

@app.route('/save_sketch', methods=['POST'])
def save_sketch():
    if 'user' not in session:
        return redirect('/')
    data_url = request.form['image_data']
    if not data_url.startswith('data:image'):
        return "Invalid image data"
    header, encoded = data_url.split(",", 1)
    binary_data = base64.b64decode(encoded)
    filename = f"{session['user']}_sketch.png"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, "wb") as f:
        f.write(binary_data)
    return redirect(url_for('match_sketch', filename=filename))

@app.route('/match_sketch/<filename>')
def match_sketch(filename):
    if 'user' not in session:
        return redirect('/')
    sketch_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    best_image, best_data, confidence = find_best_match(sketch_path)
    if best_image and best_data:
        return render_template("match_result.html",
                               matched=True,
                               sketch_img=f"/static/uploads/{filename}",
                               criminal_img=f"/static/criminals/{best_image}",
                               criminal=best_data,
                               confidence=confidence)
    else:
        return render_template("match_result.html", matched=False)

@app.route('/start_live_detection')
def start_live_detection():
    if 'user' not in session:
        return redirect('/')
    return render_template('live_detection.html')

@app.route('/process_live_match', methods=['POST'])
def process_live_match():
    if 'user' not in session:
        return redirect('/')
    data_url = request.form['image_data']
    if not data_url.startswith('data:image'):
        return "Invalid image data"
    header, encoded = data_url.split(",", 1)
    binary_data = base64.b64decode(encoded)
    filename = f"{session['user']}_live.png"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, "wb") as f:
        f.write(binary_data)
    return redirect(url_for('match_sketch', filename=filename))

@app.errorhandler(413)
def request_entity_too_large(error):
    return "Uploaded image is too large. Try reducing resolution.", 413

@app.route('/add_criminal', methods=['GET', 'POST'])
def add_criminal():
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        crime = request.form['crime']
        location = request.form['location']
        arrest_date = request.form['arrest_date']
        status = request.form['status']
        file = request.files['photo']
        
        # Add file type validation
        if file and get_mime_type(file.filename) not in ["image/jpeg", "image/png"]:
            return "Invalid file type. Only JPG and PNG are allowed.", 400

        filename = secure_filename(file.filename)
        photo_path = os.path.join(CRIMINAL_FOLDER, filename)
        file.save(photo_path)

        if os.path.exists('criminals.csv'):
            df = pd.read_csv('criminals.csv')
        else:
            df = pd.DataFrame(columns=['name','age','image','crime_type','location','arrest_date','status'])

        df.loc[len(df.index)] = {
            'name': name, 'age': age, 'crime_type': crime, 'location': location,
            'arrest_date': arrest_date, 'status': status, 'image': filename
        }
        df.to_csv('criminals.csv', index=False)
        return redirect('/dashboard')
    return render_template('add_criminal.html')

@app.route("/search_criminal", methods=["POST"])
def search_criminal():
    user_input = request.json.get("text", "").strip()
    if not user_input:
        return jsonify({"reply": "Please enter a name of the person you want information about."})

    # Step 1: Extract names/entities from input (use NLP if needed)
    entities = extract_entity(user_input)
    if not entities:
        return jsonify({"reply": "Could not understand whom you are asking about. Please provide full name(s)."})

    # Step 2: Query criminal database
    results = []
    for name in entities:
        info = fetch_criminal_info(name)
        if info:
            formatted_info = "\n".join([f"{k.capitalize()}: {v}" for k, v in info.items()])
            results.append(formatted_info)

    # Step 3: Handle no results
    if not results:
        return jsonify({"reply": "No criminal info available for the given name(s)."})

    # Step 4: Return results as assistant reply
    return jsonify({"reply": "\n\n".join(results)})
                     

                 # pdflogic

# ----------------------------
# Improved PDF generator
# ----------------------------
def build_fir_and_pdf(fir_data: dict):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "", 12)

    # Current date & time for report
    report_datetime = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    # 1. HEADER
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "1. HEADER", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"REPORT NO: {fir_data.get('report_no','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"POLICE STATION: {fir_data.get('police_station','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"DATE & TIME OF REPORT: {report_datetime}", ln=True)

    pdf.ln(4)

    # 2. INCIDENT OVERVIEW
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "2. INCIDENT OVERVIEW", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Type of Offence: {fir_data.get('offence_type','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"IPC Section(s): {fir_data.get('ipc_sections','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Date of Incident: {fir_data.get('incident_date_time','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Location of Incident: {fir_data.get('location','Not Provided')}", ln=True)
    pdf.multi_cell(0, 8, f"Incident Detail: {fir_data.get('incident_description','Not Provided')}")
    pdf.multi_cell(0, 8, f"Summary of Incident: {fir_data.get('summary','Summary generation failed.')}")

    pdf.ln(4)

    # 3. INVOLVED PARTIES
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "3. INVOLVED PARTIES", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Complainant Name: {fir_data.get('complainant_name','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Complainant Contact: {fir_data.get('contact','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Victim(s): {fir_data.get('victims','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Suspect(s): {fir_data.get('suspects','unknown')}", ln=True)
    pdf.cell(0, 8, f"Witness(es): {fir_data.get('witnesses','NA')}", ln=True)

    pdf.ln(4)

    # 4. INVESTIGATING
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "4. INVESTIGATING", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Investigating Officer: {fir_data.get('investigating_officer','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Digital Signature: {fir_data.get('digital_signature','')}", ln=True)

    # Output PDF file
    pdf_filename = f"static/fir_{int(time.time())}.pdf"
    pdf.output(pdf_filename)

    # Return only completion message and PDF path
    return f"/{pdf_filename}"

# ----------------------------
# Updated /chat_fir route
# ----------------------------
@app.route("/chat_fir", methods=["POST"])
def chat_fir():
    try:
        user_message = request.json.get("message", "").strip()
        if not user_message:
            return jsonify({"next_question": "Please type something to start."})

        # ---------- Start FIR Process ----------
        if user_message.lower() == "start_fir_process":
            session["fir_data"] = {}
            session["fir_step"] = 0
            session["dynamic_questions"] = []
            session["dynamic_index"] = 0
            session["after_index"] = 0

            session["fixed_before"] = [
                "Please provide the REPORT NUMBER.",
                "Enter the POLICE STATION.",
                "Enter TYPE OF OFFENCE (e.g., Theft, Murder).",
                "Enter IPC SECTION(s) (e.g., 379, 420).",
                "Enter DATE & TIME OF INCIDENT (dd-mm-yyyy, hh:mm AM/PM).",
                "Enter LOCATION OF INCIDENT.",
                "Describe the INCIDENT in detail."
            ]
            session["keys_before"] = [
                "report_no", "police_station", "offence_type",
                "ipc_sections", "incident_date_time", "location",
                "incident_description"
            ]
            session["fixed_after"] = [
                "Complainant Name:",
                "Complainant Contact Number:",
                "Victim(s) Name(s):",
                "Suspect(s) Name(s) (if unknown, type 'Unknown'):",
                "Witness(es) Name(s):",
                "Investigating Officer Name:",
                "Digital Signature (optional):"
            ]
            session["keys_after"] = [
                "complainant_name", "contact", "victims", "suspects",
                "witnesses", "investigating_officer", "digital_signature"
            ]

            return jsonify({"next_question": session["fixed_before"][0]})

        # ---------- Ensure FIR is started ----------
        if "fir_data" not in session:
            return jsonify({"next_question": "Please start FIR process by typing 'start_fir_process'."})

        fir_data = session["fir_data"]
        step = session["fir_step"]
        fixed_before = session["fixed_before"]
        keys_before = session["keys_before"]
        fixed_after = session["fixed_after"]
        keys_after = session["keys_after"]

        # ---------- Handle fixed_before ----------
        if step < len(fixed_before):
            if step > 0:
                fir_data[keys_before[step - 1]] = user_message

            session["fir_step"] += 1
            step += 1

            if step == len(fixed_before):
                incident_text = user_message
                offence_type = fir_data.get("offence_type", "")
                dynamic_qs = safe_generate_questions(
                    f"Offence: {offence_type}\nIncident: {incident_text}"
                )
                session["dynamic_questions"] = dynamic_qs
                session["dynamic_index"] = 0
                return jsonify({"next_question": session["dynamic_questions"][0]})
            else:
                return jsonify({"next_question": fixed_before[step]})

        # ---------- Handle dynamic questions ----------
        if session.get("dynamic_questions") and session["dynamic_index"] < len(session["dynamic_questions"]):
            idx = session["dynamic_index"]
            fir_data[f"dynamic_answer_{idx+1}"] = user_message
            session["dynamic_index"] += 1

            if session["dynamic_index"] < len(session["dynamic_questions"]):
                return jsonify({"next_question": session["dynamic_questions"][session["dynamic_index"]]})
            else:
                # Generate FIR summary for PDF
                fir_prompt = f"""
You are Astitva, a professional police investigator. 
Based on the details provided below, generate a clear and concise FIR summary in 3-5 sentences. 
Write it as if you are officially documenting the incident.

Offence Type: {fir_data.get('offence_type')}
Incident Description: {fir_data.get('incident_description')}
Other collected information: {json.dumps({k:v for k,v in fir_data.items() if k.startswith('dynamic_answer_')}, indent=2)}

Make sure to include the key facts, involved parties, and the sequence of events. 
Do not add any extra commentary or warnings. Return plain text only.
"""
                summary_text = generate_response_safe(fir_prompt, max_tokens=700) or "Summary generation failed."
                fir_data["summary"] = summary_text
                session["after_index"] = 0
                return jsonify({"next_question": fixed_after[0]})

        # ---------- Handle fixed_after ----------
        after_idx = session.get("after_index", 0)
        if 0 <= after_idx < len(keys_after):
            fir_data[keys_after[after_idx]] = user_message
            session["after_index"] = after_idx + 1

            if session["after_index"] < len(fixed_after):
                return jsonify({"next_question": fixed_after[session['after_index']]})
            else:
                # Build PDF and clear session
                pdf_path = build_fir_and_pdf(fir_data)
                session.clear()
                return jsonify({
                    "reply": "✅ FIR generation completed successfully.",
                    "download_link": pdf_path
                })

        return jsonify({"next_question": "Unexpected step. Please restart with 'start_fir_process'."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"reply": f"⚠️ Server error: {str(e)}"})









# ----------------------------
# Run App
# ----------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)

