def get_criminal_info(name):
    try:
        with open("criminals.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["name"].lower() == name.lower():
                    return row
        return None
    except Exception as e:
        print(f"[ERROR] CSV lookup failed: {e}")
        return None

@app.route("/search_criminal", methods=["POST"])
def search_criminal():
    name = request.json.get("name")
    info = get_criminal_info(name)
    reply = f"Criminal Info: {info}" if info else "No info found for this name."
    return jsonify({"reply": reply})

@app.route("/write_fir", methods=["POST"])
def write_fir():
    details = request.json.get("details")
    prompt = f"Write a structured FIR report based on: {details}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response["choices"][0]["message"]["content"]
    return jsonify({"reply": answer})