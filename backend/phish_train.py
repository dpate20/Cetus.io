from __future__ import annotations
from pathlib import Path
import os, sqlite3, pandas as pd, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.utils import shuffle
import re

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "emails.csv"
MODEL_PATH = BASE_DIR / "phishing_model.pkl"
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "phishing.db"))

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")
CARD_RE  = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
NUM_RE   = re.compile(r"\b\d{4,}\b")
URL_RE   = re.compile(r"https?://\S+")

def sanitize(text: str) -> str:
    def url_mask(m):
        url = m.group(0)
        domain = re.sub(r"^https?://", "", url).split("/")[0]
        return f"[URL:{domain}]"
    t = text or ""
    t = EMAIL_RE.sub("[EMAIL]", t)
    t = PHONE_RE.sub("[PHONE]", t)
    t = CARD_RE.sub("[CARD]", t)
    t = NUM_RE.sub("[NUM]", t)
    t = URL_RE.sub(url_mask, t)
    return t

def ensure_dataset():
    if DATA_PATH.exists():
        return
    samples = [
        ("Urgent: Your account will be closed. Click here to verify your password now.", "phish"),
        ("Security alert: Unusual sign-in attempt detected. Confirm your identity.", "phish"),
        ("Invoice for services rendered attached. Let me know if corrections needed.", "ham"),
        ("Team standup moved to 10 AM. See calendar invite.", "ham"),
        ("We noticed a problem with your payment method. Update card info immediately.", "phish"),
        ("Lunch at the student union tomorrow?", "ham"),
        ("Congratulations! You won a gift card. Claim now by entering your details.", "phish"),
        ("Weekly project update attached with action items.", "ham"),
    ]
    pd.DataFrame(samples, columns=["text", "label"]).to_csv(DATA_PATH, index=False)

def load_db_rows():
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as con:
        cur = con.execute("SELECT subject, sender, text, label FROM reports ORDER BY id ASC;")
        return cur.fetchall()

def main():
    ensure_dataset()
    df = pd.read_csv(DATA_PATH).dropna()
    seed_X = df["text"].apply(sanitize).tolist()
    seed_y = df["label"].tolist()

    rows = load_db_rows()
    if rows:
        db_X = [f"SUBJECT: {sanitize(s)}\nFROM: {sanitize(f)}\nBODY: {sanitize(t)}" for s, f, t, _ in rows]
        db_y = [lab for _, _, _, lab in rows]
        X = seed_X + db_X
        y = seed_y + db_y
    else:
        X, y = seed_X, seed_y

    X, y = shuffle(X, y, random_state=42)
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(stop_words="english", max_df=0.85)),
        ("rf", RandomForestClassifier(n_estimators=300, random_state=42)),
    ])
    pipe.fit(X, y)
    joblib.dump(pipe, MODEL_PATH)
    print(f"[OK] Trained and saved model to {MODEL_PATH} using {len(X)} samples")

if __name__ == "__main__":
    main()
