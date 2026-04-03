# 🌐 GeoAlert v2 — Smart Commodity Price Impact Monitor

> MCA Major Project — AI-Powered Global Event → Commodity Price Intelligence

---

## 📌 What It Does

GeoAlert monitors real-time global news (geopolitical conflicts, energy crises, natural disasters) and predicts how they will impact everyday commodity prices in India (LPG, Petrol, Wheat, Edible Oil).

---

## ✨ Features

| Feature | Status |
|---|---|
| Live RSS news feed (BBC, Reuters, The Hindu) | ✅ |
| Geopolitical → commodity impact classification | ✅ |
| Smart buy recommendations | ✅ |
| SQLite database with persistent storage | ✅ |
| Keyword search + category/severity filters | ✅ |
| Price trend history chart (Chart.js) | ✅ |
| Email alert on critical events | ✅ |
| User login & registration (Flask-Login) | ✅ |
| Deployable to Render.com | ✅ |

---

## 🚀 How to Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python app.py

# 3. Open browser
# http://127.0.0.1:5000
```

---

## 🌐 Deploy to Render (Free)

1. Push this folder to a GitHub repository
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` and deploys
5. Get a free live URL like `https://geoalert.onrender.com`

---

## 📧 Email Alerts Setup (Optional)

Set these environment variables:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=your-app-password
```
> Use Gmail App Passwords (not your main password). Enable 2FA on Gmail first.

---

## 🏗️ Architecture

```
User Browser
    │
    ▼
Flask Web Server (app.py)
    ├── /api/news         → Fetch & classify RSS feeds
    ├── /api/commodities  → Map events to commodities
    ├── /api/price-history→ Price trend chart data
    ├── /api/news/search  → Search stored DB articles
    └── /history          → View stored event history
    │
    ▼
SQLite Database (geoalert.db)
    ├── articles table   → Persisted news articles
    ├── users table      → User accounts
    └── price_history    → Historical price data
```

---

## 👨‍💻 Tech Stack

- **Backend**: Python, Flask, Flask-Login
- **Database**: SQLite (persistent)
- **Frontend**: HTML, CSS, JavaScript, Chart.js
- **Data**: RSS Feeds (BBC, Reuters, The Hindu, ReliefWeb)
- **Deployment**: Render.com (free tier)

---

## 📸 Screenshots

*(Add screenshots of the dashboard, history page, and login page here)*

---

*Built as MCA Major Project — 12 Credit Evaluation*
