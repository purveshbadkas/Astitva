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
import traceback
from serpapi import GoogleSearch # <--- ADD THIS LINE

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
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not set in environment")
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-preview-05-20",
)

# -----------------------------------------------------------
# SERPAPI/GOOGLE LENS INTEGRATION (Mocked)
# -----------------------------------------------------------
SERPAPI_KEY = os.getenv("SERPAPI_KEY")


def get_public_uploaded_url(filename):
    """
    Returns a globally accessible URL for the uploaded image.
    For local macOS testing, use 127.0.0.1.
    """
    if SERPAPI_KEY:
        return f"http://127.0.0.1:5001/static/uploads/{filename}"
    return None

def run_google_lens_search(filename):
    """
    Executes the Google Lens search using SerpApi and returns all data types.
    """
    lens_results = []
    lens_public_url = get_public_uploaded_url(filename)
    lens_available = bool(lens_public_url and SERPAPI_KEY) 
    
    # Initialize new variables to ensure they are defined even if API call fails or is skipped
    knowledge_graph = {}
    related_searches = []
    web_results = []
    
    if lens_available:
        try:
            params = {
                "engine": "google_lens",
                "url": lens_public_url,
                "type": "all", # Request all data types
                "api_key": SERPAPI_KEY
            }
            results = GoogleSearch(params).get_dict() # Uses the mock class for now

            # Extract all relevant data sections
            knowledge_graph = results.get("knowledge_graph", {}) 
            related_searches = results.get("related_searches", [])
            web_results = results.get("organic_results", [])
            
            # Continue processing visual matches as before
            vm = results.get("visual_matches", []) or []
            for item in vm:
                lens_results.append({
                    "title": item.get("title") or item.get("source") or "Result",
                    "link": item.get("link") or item.get("source") or "#",
                    "thumbnail": item.get("thumbnail") or item.get("image"),
                    "source": item.get("source")
                })
        except Exception as e:
            print(f"Google Lens API error: {e}")

    # Return all collected data
    return lens_results, lens_public_url, lens_available, knowledge_graph, related_searches, web_results

# -----------------------------------------------------------
# GENERAL UTILITY FUNCTIONS
# -----------------------------------------------------------
def get_mime_type(filename):
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        return "image/jpeg"
    elif filename.endswith(".png"):
        return "image/png"
    return None

def generate_response(prompt, max_tokens):
    try:
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens}
        )
        if response and hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            parts = getattr(candidate.content, "parts", None)
            if parts and len(parts) > 0:
                text = getattr(parts[0], "text", "").strip()
                if text:
                    return text
        return None
    except Exception as e:
        print(f"[AI ERROR] {e}")
        return None

def generate_response_safe(prompt, max_tokens=1000,temperature=0.6):
    try:
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens, "temperature": temperature}
        )
        texts = []
        for cand in response.candidates:
            if hasattr(cand, "content") and hasattr(cand.content, "parts"):
                for part in cand.content.parts:
                    if hasattr(part, "text") and part.text:
                        texts.append(part.text.strip())
        if not texts:
            return None
        return "\n".join(texts)
    except Exception as e:
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
        if text.startswith("```json"):
            text = text.split("\n",1)[-1].rsplit("\n",1)[0].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
        try:
            questions = json.loads(text)
            if not isinstance(questions, list):
                raise ValueError("Not a list")
        except Exception:
            questions = [q.strip(" -•1234567890.") for q in text.split("\n") if q.strip()]
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
        # NOTE: Passwords should be hashed in a real application.
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
    
    # 1. Database Match
    best_image, best_data, confidence = find_best_match(sketch_path)
    
    # 2. Google Lens Search - Now receives ALL data types
    lens_results, lens_public_url, lens_available, knowledge_graph, related_searches, web_results = run_google_lens_search(filename)

    if best_image and best_data:
        return render_template("match_result.html",
                               matched=True,
                               sketch_img=f"/static/uploads/{filename}",
                               criminal_img=f"/static/criminals/{best_image}",
                               criminal=best_data,
                               confidence=confidence,
                               uploaded_image=filename, 
                               # Lens context - all variables now passed
                               lens_results=lens_results,
                               lens_public_url=lens_public_url,
                               lens_available=lens_available,
                               knowledge_graph=knowledge_graph,
                               related_searches=related_searches,
                               web_results=web_results
                               )
    else:
        return render_template("match_result.html", 
                               matched=False,
                               uploaded_image=filename,
                               # Lens context - all variables now passed
                               lens_results=lens_results,
                               lens_public_url=lens_public_url,
                               lens_available=lens_available,
                               knowledge_graph=knowledge_graph,
                               related_searches=related_searches,
                               web_results=web_results
                               )

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

#----------------------------
# AI-powered Name Extractor
#----------------------------
def extract_name_with_ai(user_input):
    prompt = f"""
    Extract ONLY the full name of a person from the following query. If no full name is found, return the word "None".

    Query: "{user_input}"
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 200},
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )
        
        if not response or not response.candidates:
            return None
        if not hasattr(response.candidates[0].content, 'parts') or not response.candidates[0].content.parts:
            return None

        text = response.candidates[0].content.parts[0].text.strip()
        
        if text.lower() != 'none':
            return text.strip().strip('"').strip("'")
        return None

    except Exception as e:
        print(f"[AI ERROR] Name extraction failed: {e}")
        return None


#----------------------------
# Updated /search_criminal route
#----------------------------
@app.route("/search_criminal", methods=["POST"])
def search_criminal():
    user_input = request.json.get("text", "").strip()
    if not user_input:
        return jsonify({"reply": "Please enter a name of the person you want information about."})

    name_to_search = extract_name_with_ai(user_input)
    
    if not name_to_search:
        doc = nlp(user_input)
        entities = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        if entities:
            name_to_search = entities[0]

    if not name_to_search:
        return jsonify({"reply": "I couldn't identify a name in your request. Please provide a clearer name."})
    
    name_to_search_standardized = name_to_search.title()

    info = fetch_criminal_info(name_to_search_standardized)

    if not info:
        return jsonify({"reply": f"No criminal info available for {name_to_search_standardized}."})

    formatted_info = "\n".join([f"{k.capitalize()}: {v}" for k, v in info.items()])
    return jsonify({"reply": formatted_info})
                     
# ----------------------------
# Improved PDF generator
# ----------------------------
def build_fir_and_pdf(fir_data: dict):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "", 12)

    report_datetime = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "HEADER", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"REPORT NO: {fir_data.get('report_no','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"POLICE STATION: {fir_data.get('police_station','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"DATE & TIME OF REPORT: {report_datetime}", ln=True)

    pdf.ln(4)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "INCIDENT OVERVIEW", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Type of Offence: {fir_data.get('offence_type','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"IPC Section(s): {fir_data.get('ipc_sections','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Date and Tiine of Incident: {fir_data.get('incident_date_time','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Location of Incident: {fir_data.get('location','Not Provided')}", ln=True)
    pdf.multi_cell(0, 8, f"Incident Detail: {fir_data.get('incident_description','Not Provided')}")
    pdf.cell(0, 8, "Summary of Incident:", ln=True)
    pdf.multi_cell(180, 8, f"    {fir_data.get('summary', 'Summary generation failed.')}", align='L')

    pdf.ln(4)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "INVOLVED PARTIES", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Complainant Name: {fir_data.get('complainant_name','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Complainant Contact: {fir_data.get('contact','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Victim(s): {fir_data.get('victims','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Suspect(s): {fir_data.get('suspects','unknown')}", ln=True)
    pdf.cell(0, 8, f"Witness(es): {fir_data.get('witnesses','NA')}", ln=True)

    pdf.ln(4)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "INVESTIGATING", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Investigating Officer: {fir_data.get('investigating_officer','Not Provided')}", ln=True)
    pdf.cell(0, 8, f"Digital Signature: {fir_data.get('digital_signature','')}", ln=True)

    pdf_filename = f"static/fir_{int(time.time())}.pdf"
    pdf.output(pdf_filename)

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

        if "fir_data" not in session:
            return jsonify({"next_question": "Please start FIR process by typing 'start_fir_process'."})

        fir_data = session["fir_data"]
        step = session["fir_step"]
        fixed_before = session["fixed_before"]
        keys_before = session["keys_before"]
        fixed_after = session["fixed_after"]
        keys_after = session["keys_after"]

        if step < len(fixed_before):
            fir_data[keys_before[step]] = user_message

            session["fir_step"] += 1
            step += 1

            if step == len(fixed_before):
                incident_text = fir_data.get("incident_description", "")
                offence_type = fir_data.get("offence_type", "")
                dynamic_qs = safe_generate_questions(
                    f"Offence: {offence_type}\nIncident: {incident_text}"
                )
                session["dynamic_questions"] = dynamic_qs
                session["dynamic_index"] = 0
                return jsonify({"next_question": session["dynamic_questions"][0]})
            else:
                return jsonify({"next_question": fixed_before[step]})

        if session.get("dynamic_questions") and session["dynamic_index"] < len(session["dynamic_questions"]):
            idx = session["dynamic_index"]
            fir_data[f"dynamic_answer_{idx+1}"] = user_message
            session["dynamic_index"] += 1

            if session["dynamic_index"] < len(session["dynamic_questions"]):
                return jsonify({"next_question": session["dynamic_questions"][session["dynamic_index"]]})
            else:
                fir_prompt = f"""
You are Astitva, a professional police investigator. Generate a concise 8-10 sentence FIR summary using the following details.
Offence Type: {fir_data.get('offence_type', 'Not provided')}
Incident Description: {fir_data.get('incident_description', 'Not provided')}
Other collected information: {json.dumps({k:v for k,v in fir_data.items() if k.startswith('dynamic_answer_')})}

Return only plain text, do not include markdown or JSON.
"""
                summary_text = generate_response_safe(fir_prompt, max_tokens=1000, temperature=0.6)
                fir_data["summary"] = summary_text or "Summary generation failed."
                session["after_index"] = 0
                return jsonify({"next_question": fixed_after[0]})

        after_idx = session.get("after_index", 0)
        if 0 <= after_idx < len(keys_after):
            fir_data[keys_after[after_idx]] = user_message
            session["after_index"] = after_idx + 1

            if session["after_index"] < len(fixed_after):
                return jsonify({"next_question": fixed_after[session['after_index']]})
            else:
                pdf_path = build_fir_and_pdf(fir_data)
                session.clear()
                return jsonify({
                    "reply": "✅ FIR generation completed successfully.",
                    "download_link": pdf_path
                })

        return jsonify({"next_question": "Unexpected step. Please restart with 'start_fir_process'."})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"⚠️ Server error: {str(e)}"})


# ----------------------------
# Run App
# ----------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)