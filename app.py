from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3
import os
import base64
import face_recognition
import pandas as pd

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
    try:
        sketch_img = face_recognition.load_image_file(sketch_path)
        sketch_encodings = face_recognition.face_encodings(sketch_img)
        if not sketch_encodings:
            return render_template("match_result.html", matched=False)
        sketch_encoding = sketch_encodings[0]
    except Exception as e:
        return f"Error reading sketch: {e}"

    def face_distance_to_confidence(face_distance, threshold=0.6):
        if face_distance > threshold:
            range_val = (1.0 - threshold)
            linear_val = (1.0 - face_distance) / (range_val * 2.0)
            return linear_val
        else:
            range_val = threshold
            linear_val = 1.0 - (face_distance / (range_val * 2.0))
            return linear_val + ((1.0 - linear_val) * ((linear_val - 0.5) ** 0.2))

    df = pd.read_csv('criminals.csv')
    for _, row in df.iterrows():
        criminal_img_path = os.path.join('static', 'criminals', row['image'])
        try:
            criminal_img = face_recognition.load_image_file(criminal_img_path)
            criminal_encodings = face_recognition.face_encodings(criminal_img)
            if not criminal_encodings:
                continue
            criminal_encoding = criminal_encodings[0]
            face_distance = face_recognition.face_distance([criminal_encoding], sketch_encoding)[0]
            match = face_recognition.compare_faces([criminal_encoding], sketch_encoding)[0]
            if match:
                confidence = face_distance_to_confidence(face_distance) * 100
                return render_template("match_result.html",
                                       matched=True,
                                       sketch_img=f"/static/uploads/{filename}",
                                       criminal_img=f"/static/criminals/{row['image']}",
                                       criminal=row.to_dict(),
                                       confidence=round(confidence, 2))
        except:
            continue

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

    print(f"📦 Received base64 image size: {len(data_url) / 1024:.2f} KB")

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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0',port=5001,debug=True)
