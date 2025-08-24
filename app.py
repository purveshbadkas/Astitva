from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import sqlite3
import base64
import pandas as pd
import os
from datetime import datetime

# Google AI
import google.generativeai as genai
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not set in environment")
genai.api_key = GOOGLE_API_KEY

# Face matching
from face_matcher import find_best_match

import spacy
import re

nlp = spacy.load("en_core_web_sm")

def extract_entity(text):
    # Extract PERSON entities using spaCy
    doc = nlp(text)
    entities = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    
    # Fallback: look for patterns like "about <name>" or "on <name>"
    fallback_matches = re.findall(r"(?:about|on)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", text)
    
    if fallback_matches:
        entities.extend(fallback_matches)
    
    # Remove duplicates
    return list(set(entities))



app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
app.secret_key = 'your_secret_key'

# Upload folders
UPLOAD_FOLDER = os.path.join('static', 'uploads')
CRIMINAL_FOLDER = os.path.join('static', 'criminals')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CRIMINAL_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
        filename = secure_filename(file.filename)
        photo_path = os.path.join(CRIMINAL_FOLDER, filename)
        file.save(photo_path)

        df = pd.read_csv('criminals.csv') if os.path.exists('criminals.csv') else pd.DataFrame(columns=[
            'name', 'age', 'crime_type', 'location', 'arrest_date', 'status', 'image'
        ])
        df.loc[len(df.index)] = {
            'name': name,
            'age': age,
            'crime_type': crime,
            'location': location,
            'arrest_date': arrest_date,
            'status': status,
            'image': filename
        }
        df.to_csv('criminals.csv', index=False)

        return redirect('/dashboard')
    return render_template('add_criminal.html')

# ---------------- FIR Generation ----------------
@app.route("/write_fir", methods=["POST"])
def write_fir():
    data = request.json
    details = data.get("details")
    if not details or len(details) < 20:
        return jsonify({"reply": "Please provide detailed information for FIR."}), 400

    fir_text = f"""
    Maharashtra Police FIR

    FIR Number: AUTO-GENERATED
    Date: {datetime.now().strftime('%d-%m-%Y')}
    Complainant: Anonymous
    Location: Unknown
    
    Incident Description:
    {details}

    Suspect Info:
    Not Provided

    Action Taken:
    Pending
    """

    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in fir_text.strip().split("\n"):
        pdf.multi_cell(0, 8, line)
    pdf_filename = "static/fir_preview.pdf"
    pdf.output(pdf_filename)

    return jsonify({"reply": fir_text, "pdf_url": f"/{pdf_filename}"})

# ---------------- Criminal Search with NLP ----------------
@app.route("/search_criminal", methods=["POST"])
def search_criminal():
    # Accept full prompt from frontend
    user_input = request.json.get("text")  
    if not user_input or not user_input.strip():
        return jsonify({"reply": "Please enter something to search."})

    # Extract names/entities from the input using spaCy or your NLP function
    entities = extract_entity(user_input)  # returns a list of names like ["Virat Kohli"]

    if not entities:
        return jsonify({"reply": "Could not understand whom you are asking about."})

    results = []
    for name in entities:
        info = fetch_criminal_info(name)  # your existing function to get info
        if info:
            results.append("\n".join([f"{k.capitalize()}: {v}" for k, v in info.items()]))

    if not results:
        return jsonify({"reply": "No criminal info available for the given name(s)."})

    # Join all results
    return jsonify({"reply": "\n\n".join(results)})

# ----------------------------
# Run App
# ----------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
