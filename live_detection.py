from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3
import os
import base64
import face_recognition
import pandas as pd
import time
import cv2
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Upload folder config
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# DB setup
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            return redirect('/')
        except sqlite3.IntegrityError:
            return "Username already taken"
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    if user:
        session['user'] = username
        return redirect('/dashboard')
    return "Invalid credentials"

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

    if 'sketch' not in request.files:
        return "No file part in request"

    file = request.files['sketch']
    if file.filename == '':
        return "No selected file"

    if file:
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

    try:
        header, encoded = data_url.split(",", 1)
        binary_data = base64.b64decode(encoded)
    except Exception as e:
        return f"Failed to decode image: {e}"

    filename = f"{session['user']}_sketch.png"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        with open(filepath, "wb") as f:
            f.write(binary_data)
    except Exception as e:
        return f"Failed to save image: {e}"

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

    df = pd.read_csv('criminals.csv')
    for _, row in df.iterrows():
        criminal_img_path = os.path.join('static', 'criminals', row['image'])
        try:
            criminal_img = face_recognition.load_image_file(criminal_img_path)
            criminal_encodings = face_recognition.face_encodings(criminal_img)
            if not criminal_encodings:
                continue
            criminal_encoding = criminal_encodings[0]

            result = face_recognition.compare_faces([criminal_encoding], sketch_encoding)[0]
            if result:
                return render_template("match_result.html",
                                       matched=True,
                                       sketch_img=f"/static/uploads/{filename}",
                                       criminal_img=f"/static/criminals/{row['image']}",
                                       criminal=row)
        except:
            continue

    return render_template("match_result.html", matched=False)

# ========== Live Detection ==========
@app.route('/live_detection')
def live_detection():
    return render_template('live_detection.html')

def run_live_recognition():
    known_encodings = []
    known_names = []

    df = pd.read_csv("criminals.csv")
    for _, row in df.iterrows():
        image_path = os.path.join("static", "criminals", row['image'])
        try:
            image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(image)[0]
            known_encodings.append(encoding)
            known_names.append(row['name'])
        except:
            continue

    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = small_frame[:, :, ::-1]

        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            matches = face_recognition.compare_faces(known_encodings, face_encoding)
            name = "Unknown"

            if True in matches:
                first_match_index = matches.index(True)
                name = known_names[first_match_index]

            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        cv2.imshow("Live Recognition - Press 'q' to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

@app.route('/start_live_detection')
def start_live_detection():
    thread = threading.Thread(target=run_live_recognition)
    thread.daemon = True  # Ensure thread exits when Flask exits
    thread.start()
    return redirect('/live_detection')

# 🚀 Run the app
if __name__ == '__main__':
    init_db()
    app.run(debug=True)

