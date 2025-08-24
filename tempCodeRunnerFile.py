@app.route("/write_fir", methods=["POST"])
def write_fir():
    data = request.json
    required_fields = ["date", "complainant", "location", "incident_description", "suspect_info", "action_taken"]

    # Validate all fields
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"reply": f"Missing field: {field}"}), 400

    # Create FIR text (Maharashtra State Police format)
    fir_text = f"""
    Maharashtra Police FIR

    FIR Number: AUTO-GENERATED
    Date: {data['date']}
    Complainant: {data['complainant']}
    Location: {data['location']}
    
    Incident Description:
    {data['incident_description']}

    Suspect Info:
    {data['suspect_info']}

    Action Taken:
    {data['action_taken']}
    """

    # Generate PDF
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in fir_text.strip().split("\n"):
        pdf.multi_cell(0, 8, line)
    pdf_filename = "static/fir_preview.pdf"
    pdf.output(pdf_filename)

    return jsonify({"reply": fir_text, "pdf_url": f"/{pdf_filename}"})


# ---------------- Criminal Search ----------------
def get_criminal_info(name):
    """Look up criminal info from CSV and return as dict."""
    if not name:
        return None
    csv_path = os.path.join(os.path.dirname(__file__), "criminals.csv")
    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row = {k.strip().lower(): v.strip() for k, v in row.items()}
                if row.get("name") == name.strip().lower():
                    return row
        return None
    except Exception as e:
        print(f"[ERROR] CSV lookup failed: {e}")
        return None

def format_criminal_info(info):
    """Format criminal info dictionary into readable string."""
    if not info:
        return "No information available."
    return "\n".join([f"{key.capitalize()}: {value}" for key, value in info.items() if value])

@app.route("/search_criminal", methods=["POST"])
def search_criminal():
    name = request.json.get("name")
    info = get_criminal_info(name)
    return jsonify({"reply": format_criminal_info(info)})


# ----------------------------
# Run App
# ----------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
