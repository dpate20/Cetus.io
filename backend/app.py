from __future__ import annotations
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import os, re, sqlite3, joblib

# ------------------------
# Paths & Globals
# ------------------------
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "phishing_model.pkl"
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "phishing.db"))  # set DB_PATH in prod for persistence

app = Flask(__name__)
# MVP: wide-open CORS for testing. Lock down in prod.
CORS(app, resources={r"/*": {"origins": ["*"]}})

# ------------------------
# DB Helpers
# ------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            sender  TEXT,
            text    TEXT,
            label   TEXT CHECK(label IN ('phish','ham')) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""")
        con.commit()

def db_insert(subject: str, sender: str, text: str, label: str):
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO reports(subject, sender, text, label) VALUES(?,?,?,?)",
                    (subject, sender, text, label))
        con.commit()

def db_fetch_all():
    with sqlite3.connect(DB_PATH) as con:
        cur = con.execute("SELECT subject, sender, text, label FROM reports ORDER BY id ASC;")
        rows = cur.fetchall()
    return rows

def db_count():
    with sqlite3.connect(DB_PATH) as con:
        (n,) = con.execute("SELECT COUNT(*) FROM reports;").fetchone()
    return int(n)

# ------------------------
# Sanitization (privacy)
# ------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")
CARD_RE  = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
NUM_RE   = re.compile(r"\b\d{4,}\b")
URL_RE   = re.compile(r"https?://\S+")

def sanitize(text: str) -> str:
    t = text or ""
    t = EMAIL_RE.sub("[EMAIL]", t)
    t = PHONE_RE.sub("[PHONE]", t)
    t = CARD_RE.sub("[CARD]", t)
    t = NUM_RE.sub("[NUM]", t)
    # Keep domain hint while redacting full URL
    def url_mask(m):
        url = m.group(0)
        # extract domain-ish part
        domain = re.sub(r"^https?://", "", url).split("/")[0]
        return f"[URL:{domain}]"
    t = URL_RE.sub(url_mask, t)
    return t

# ------------------------
# Model bootstrap & training
# ------------------------
def _seed_pipe():
    from sklearn.pipeline import Pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    return Pipeline([
        ("tfidf", TfidfVectorizer(stop_words="english", max_df=0.9)),
        ("rf", RandomForestClassifier(n_estimators=300, random_state=42)),
    ])

def _seed_data():
    # Minimal starter data so the API works out of the box
    texts = [
        "Urgent action required! Verify your password now or your account will be suspended.",
        "Your package is waiting. Enter your card number to schedule delivery.",
        "Quarterly update: Please find the meeting notes attached and let me know if you have questions.",
        "Lunch tomorrow at 12?",
    ]
    labels = ["phish", "phish", "ham", "ham"]
    return texts, labels

def train_from_db_and_seed(save=True):
    from sklearn.utils import shuffle
    pipe = _seed_pipe()
    seed_X, seed_y = _seed_data()

    # Pull sanitized rows from DB
    rows = db_fetch_all()
    if rows:
        db_X = []
        db_y = []
        for subj, snd, txt, lab in rows:
            blob = f"SUBJECT: {sanitize(subj)}\nFROM: {sanitize(snd)}\nBODY: {sanitize(txt)}"
            db_X.append(blob)
            db_y.append(lab)
        X = seed_X + db_X
        y = seed_y + db_y
    else:
        X, y = seed_X, seed_y

    X, y = shuffle(X, y, random_state=42)
    pipe.fit(X, y)
    if save:
        joblib.dump(pipe, MODEL_PATH)
    return pipe

def load_or_bootstrap_model():
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    # No model? train from (empty) DB + seed
    return train_from_db_and_seed(save=True)

# Initialize DB + model
init_db()
model = load_or_bootstrap_model()

# ------------------------
# Routes
# ------------------------
@app.get("/ping")
def ping():
    return jsonify({"ok": True, "reports": db_count()})

@app.post("/predict")
def predict():
    data = request.get_json(silent=True) or {}
    subject = (data.get("subject") or "").strip()
    sender  = (data.get("from") or "").strip()
    text    = (data.get("text") or "").strip()

    blob = f"SUBJECT: {sanitize(subject)}\nFROM: {sanitize(sender)}\nBODY: {sanitize(text)}"
    pred = model.predict([blob])[0]
    label = "Phishing" if str(pred).lower().startswith("phish") else "Legit"

    conf = None
    try:
        proba = model.predict_proba([blob])[0]
        classes = getattr(model, "classes_", None)
        if classes is not None and len(classes) == 2:
            idx = list(classes).index("phish") if "phish" in classes else (1 if label == "Phishing" else 0)
            conf = float(proba[idx])
    except Exception:
        pass

    return jsonify({"prediction": label, "confidence": conf})

@app.post("/report")
def report():
    """
    Add a labeled example to the DB and retrain so the model learns new scams.
    Body: { subject, from, text, label: "phish" | "ham" }
    """
    data = request.get_json(silent=True) or {}
    subject = (data.get("subject") or "")
    sender  = (data.get("from") or "")
    text    = (data.get("text") or "")
    label   = str(data.get("label") or "phish").lower()
    if label not in ("phish", "ham"):
        return jsonify({"ok": False, "error": "label must be 'phish' or 'ham'"}), 400

    # Store sanitized
    db_insert(sanitize(subject), sanitize(sender), sanitize(text), label)

    # Retrain immediately so it learns right away
    global model
    model = train_from_db_and_seed(save=True)

    return jsonify({"ok": True, "reports": db_count()})

@app.get("/samples/count")
def samples_count():
    return jsonify({"count": db_count()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
