# 🛡️ Cetus — PhishDetect (Chrome Extension + Flask ML API)

**Cetus** is a Gmail-aware phishing detection tool powered by a Chrome Extension and a Flask-based ML API. It now supports **dynamic learning**: users can report new scams with one click, and the system updates its model in real-time — no new files needed, no restarts required.

---

## 🚀 Features

- 🧠 **Flask ML Backend**: TF-IDF + RandomForest trained on phishing patterns. Re-trains dynamically from user reports.
- 🔌 **Chrome Extension (MV3)**: Reads subject, sender, and body of open Gmail messages using DOM scraping.
- 📦 **SQLite Database**: Stores sanitized samples in `phishing.db` — auto-created on first run.
- 🔁 **Retrain-on-Report**: Each report triggers model re-training from the DB + seed examples.
- 🧼 **Sanitization Layer**: Masks personal data, URLs, card numbers, etc., before storage or training.

---

## 📁 File Structure

```
Cetus/
├── backend/
│   ├── app.py            # API with prediction + reporting + sanitization
│   ├── phish_train.py    # Manual training script (seed + DB)
│   └── requirements.txt
└── extension/
    ├── content.js        # Gmail scraper
    ├── popup.js          # Popup UI logic
    ├── popup.html        # Chrome extension popup
    └── manifest.json     # Chrome MV3 manifest
```

---

## 🧪 Quickstart

### ✅ Windows (PowerShell)

```powershell
cd Cetus\backend
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python phish_train.py
python app.py
```

### 🐧 macOS/Linux (bash/zsh)

```bash
cd Cetus/backend
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python phish_train.py
python app.py
```

---

## 🧩 Load the Chrome Extension

1. Go to `chrome://extensions`
2. Toggle **Developer Mode**
3. Click **Load unpacked**
4. Select the `Cetus/extension` directory
5. Open a Gmail email → open the extension popup
6. Click **"Load from Gmail"** → then **"Check Email"**
7. Help it learn: click **"Report as Phish"** or **"Report as Legit"**

> ⚠️ If Chrome gives icon warnings, either remove `default_icon` from `manifest.json` or add a 128×128 `icon.png`.

---

## 📡 API Reference

### `POST /predict`

Run a prediction on an email.

**Request:**

```json
{
  "subject": "⚠️ Your account is compromised",
  "from": "hacker@scam.com",
  "text": "Click here to reset your password..."
}
```

**Response:**

```json
{
  "prediction": "Phishing",
  "confidence": 0.91
}
```

---

### `POST /report`

Store a sample in the DB and re-train the model on the fly.

**Request:**

```json
{
  "subject": "Test subject",
  "from": "user@domain.com",
  "text": "Sample text here...",
  "label": "phish" // or "ham"
}
```

**Response:**

```json
{ "ok": true, "reports": 15 }
```

---

### `GET /ping`

Check if API is alive.

```json
{ "ok": true, "reports": 15 }
```

---

### `GET /samples/count`

Count of user-reported samples in DB.

```json
{ "count": 15 }
```

---

## 🧠 How Learning Works

- Reported emails are stored (sanitized) in SQLite (`phishing.db`)
- Each report triggers retraining using:
  - ✅ Seed examples
  - ✅ All stored samples
- No file modifications or CLI needed — happens live!

To manually retrain:  
```bash
python phish_train.py
```

---

## ☁️ Deploying to Render (No Docker Needed)

### 1. Push this repo to GitHub  
### 2. Create a new **Render Web Service**

- **Root Directory:** Leave blank or use `Cetus/`
- **Build Command:**  
  `pip install -r Cetus/backend/requirements.txt`
- **Start Command:**  
  `python Cetus/backend/app.py`
- **Python Version:** 3.11+

### 3. Add a Persistent Disk

- Go to **Disks → Add Disk**
  - Name: `cetus-data`
  - Size: `1GB`
  - Mount Path: `/var/lib/cetus`

### 4. Set Environment Variable:

```env
DB_PATH=/var/lib/cetus/phishing.db
```

> Then plug your deployed Render URL into `popup.js` (or make it configurable).

---

## 🛡️ Security Notes

- Data is sanitized: all emails, phone numbers, card numbers, URLs, and long numbers are redacted.
- No PII stored in training or reporting.
- CORS is permissive for development. Lock it down for production.
- For public deployments, add API key, rate limiting, and HTTPS.

---

⭐ Star the repo if this project helped you!
