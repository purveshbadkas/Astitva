import numpy as np
import face_recognition
import pandas as pd
import os

# --- Load criminal embeddings safely ---
def load_criminal_embeddings():
    if os.path.exists('criminal_embeddings.npy') and os.path.exists('criminals.csv'):
        embeddings = np.load('criminal_embeddings.npy', allow_pickle=True).item()
        df = pd.read_csv('criminals.csv')
        return embeddings, df
    else:
        df = pd.read_csv('criminals.csv')
        embeddings = {}
        for _, row in df.iterrows():
            img_path = os.path.join('static', 'criminals', row['image'])
            if not os.path.exists(img_path):
                print(f"⚠️ Skipping missing file: {img_path}")
                continue  # skip missing files
            try:
                img = face_recognition.load_image_file(img_path)
                encodings = face_recognition.face_encodings(img, model='large')
                if encodings:
                    embeddings[row['image']] = encodings[0]
            except Exception as e:
                print(f"⚠️ Error processing {img_path}: {e}")
                continue
        np.save('criminal_embeddings.npy', embeddings)
        return embeddings, df

# --- Convert face distance to confidence ---
def face_distance_to_confidence(face_distance, threshold=0.6):
    if face_distance > threshold:
        range_val = (1.0 - threshold)
        linear_val = (1.0 - face_distance) / (range_val * 2.0)
        return linear_val
    else:
        range_val = threshold
        linear_val = 1.0 - (face_distance / (range_val * 2.0))
        return linear_val + ((1.0 - linear_val) * ((linear_val - 0.5) ** 0.2))

# --- Find best match in the database ---
def find_best_match(uploaded_img_path):
    if not os.path.exists(uploaded_img_path):
        return None, None, "Uploaded image does not exist."

    try:
        img = face_recognition.load_image_file(uploaded_img_path)
        encodings = face_recognition.face_encodings(img, model='large')
        if not encodings:
            return None, None, "No face found in uploaded image."
        uploaded_encoding = encodings[0]
    except Exception as e:
        return None, None, f"Error reading uploaded image: {e}"

    embeddings, df = load_criminal_embeddings()

    best_match_image = None
    best_match_data = None
    highest_confidence = 0

    for filename, criminal_encoding in embeddings.items():
        face_distance = face_recognition.face_distance([criminal_encoding], uploaded_encoding)[0]
        confidence = face_distance_to_confidence(face_distance) * 100
        if confidence > highest_confidence:
            highest_confidence = confidence
            best_match_image = filename
            best_match_data = df[df['image'] == filename].iloc[0].to_dict()

    if best_match_image:
        return best_match_image, best_match_data, round(highest_confidence, 2)
    else:
        return None, None, 0
