from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import sqlite3
import base64
import pandas as pd
import csv
import google.generativeai as genai
from google.generativeai.types import ContentType
from google import genai
from flask import Flask, request, jsonify
import os

# Import your separate matching logic
from face_matcher import find_best_match

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
app.secret_key = 'your_secret_key'

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not set in environment")
genai.api_key = GOOGLE_API_KEY

api_key = os.getenv("GOOGLE_API_KEY")  # or "GOOGLE_API_KEY" if using Gemini
if not api_key:
    print("[ERROR] API key not found!")


UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ----------------------------
# Database Setup
# ----------------------------
def init_db():
    conn = sqlite3.connect('database.db')
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
    conn.close()


# ----------------------------
# Criminal Info Lookup
# ----------------------------
def fetch_criminal_info(name):
    if not os.path.exists("criminals.csv"):
        return None

    df = pd.read_csv("criminals.csv")

    # Case-insensitive partial match
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
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
    user = c.fetchone()
    conn.close()
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
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
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
    
    # Unpack the tuple returned by find_best_match
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
        photo_path = os.path.join('static', 'criminals', filename)
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

# ----------------------------
# Utility Functions
# ----------------------------

def get_criminal_info(name):
    """Look up criminal info from CSV and return as dict."""
    if not name:
        return None

    try:
        with open("criminals.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["name"].strip().lower() == name.strip().lower():
                    return row
        return None
    except Exception as e:
        print(f"[ERROR] CSV lookup failed: {e}")
        return None

def format_criminal_info(info):
    """Format criminal info dictionary into readable string."""
    if not info:
        return "No information available."
    return "\n".join([f"{key.capitalize()}: {value}" for key, value in info.items()])


# ----------------------------
# Chatbot Routes
# ----------------------------

@app.route("/write_fir", methods=["POST"])
def write_fir():
    details = request.json.get("details")
    if not details:
        return jsonify({"reply": "No details provided for FIR."})

    prompt = f"""
    You are a police AI assistant. 
    Write a professional FIR report based on the following incident details:

    {details}

    Include these headings:
    - FIR Number
    - Date
    - Complainant
    - Incident Description
    - Location
    - Suspect Info (if any)
    - Action Taken
    """

    try:
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        fir_text = response.text
        return jsonify({"reply": fir_text})

    except Exception as e:
        print(f"[ERROR] Gemini FIR generation failed: {e}")
        return jsonify({"reply": "Error generating FIR. Please check your API key and network."})




# ----------------------------
# Run App
# ----------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
