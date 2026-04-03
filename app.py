from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import feedparser
import sqlite3
import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'geoalert-secret-2024-change-in-production')

# ── LOGIN MANAGER ────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

DB = os.path.join(os.path.dirname(__file__), 'geoalert.db')

# ── USER MODEL ───────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, id, username, email, alert_email=None):
        self.id = id
        self.username = username
        self.email = email
        self.alert_email = alert_email

@login_manager.user_loader
def load_user(user_id):
    conn = get_conn()
    row = conn.execute('SELECT id, username, email, alert_email FROM users WHERE id=?', (user_id,)).fetchone()
    conn.close()
    if row:
        return User(*row)
    return None

# ── COMMODITY MAP ────────────────────────────────────────────
COMMODITY_MAP = [
    {
        'id': 'lpg',
        'name': 'LPG Cylinder',
        'icon': '🔵',
        'price': '₹903',
        'keywords': ['iran', 'iraq', 'saudi', 'opec', 'oil', 'middle east', 'crude', 'petroleum', 'fuel', 'gas'],
        'impact': 'critical',
        'reason': 'Middle East conflict detected — crude oil supply disruption expected',
        'action': 'Book LPG Now',
        'link': 'https://www.mylpg.in'
    },
    {
        'id': 'petrol',
        'name': 'Petrol / Diesel',
        'icon': '⛽',
        'price': '₹102.6/L',
        'keywords': ['iran', 'crude', 'opec', 'oil price', 'petroleum', 'refinery', 'sanctions'],
        'impact': 'critical',
        'reason': 'Crude oil price surge impacts fuel prices within 2–4 weeks',
        'action': 'Fill Tank Now',
        'link': '#'
    },
    {
        'id': 'induction',
        'name': 'Induction Stove',
        'icon': '🍳',
        'price': '₹2,499',
        'keywords': ['lpg', 'gas price', 'cylinder', 'cooking gas', 'oil', 'fuel hike'],
        'impact': 'high',
        'reason': 'LPG hike risk — induction stove is a smart alternative',
        'action': 'Buy on Amazon',
        'link': 'https://www.amazon.in/s?k=induction+stove'
    },
    {
        'id': 'wheat',
        'name': 'Wheat / Flour',
        'icon': '🌾',
        'price': '₹2,275/qtl',
        'keywords': ['russia', 'ukraine', 'wheat', 'grain', 'food', 'drought', 'harvest'],
        'impact': 'high',
        'reason': 'Russia-Ukraine conflict disrupts global wheat supply chains',
        'action': 'Stock Up',
        'link': '#'
    },
    {
        'id': 'edibleoil',
        'name': 'Edible Oil',
        'icon': '🫙',
        'price': '₹148/L',
        'keywords': ['ukraine', 'sunflower', 'palm oil', 'indonesia', 'drought', 'crop'],
        'impact': 'medium',
        'reason': 'Supply disruption from Ukraine war affects sunflower oil imports',
        'action': 'Buy in Bulk',
        'link': '#'
    },
]

SEVERITY_KEYWORDS = {
    'critical': ['war', 'attack', 'invasion', 'airstrike', 'missile', 'explosion',
                 'conflict', 'battle', 'troops', 'military', 'nuclear', 'sanctions',
                 'embargo', 'blockade', 'crisis', 'coup'],
    'high': ['tension', 'clash', 'protest', 'strike', 'flood', 'earthquake',
             'cyclone', 'hike', 'surge', 'shortage', 'disruption', 'warning', 'alert'],
    'medium': ['talks', 'negotiation', 'concern', 'monitor', 'advisory',
               'dispute', 'sanction', 'inflation', 'recession'],
}

def classify_severity(text):
    t = text.lower()
    for level, words in SEVERITY_KEYWORDS.items():
        if any(w in t for w in words):
            return level
    return 'normal'

def detect_category(text):
    t = text.lower()
    if any(w in t for w in ['iran', 'iraq', 'war', 'attack', 'military', 'nato', 'conflict']):
        return 'conflict'
    if any(w in t for w in ['oil', 'crude', 'lpg', 'gas', 'energy', 'opec', 'fuel']):
        return 'energy'
    if any(w in t for w in ['economy', 'inflation', 'rupee', 'dollar', 'gdp', 'market']):
        return 'economy'
    if any(w in t for w in ['flood', 'earthquake', 'cyclone', 'tsunami', 'disaster']):
        return 'disaster'
    return 'world'

def get_affected_commodities(text):
    t = text.lower()
    return [c['name'] for c in COMMODITY_MAP if any(k in t for k in c['keywords'])]

# ── DATABASE ─────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Articles table
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            source TEXT,
            category TEXT,
            severity TEXT,
            link TEXT,
            fetched_at TEXT
        )
    ''')
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            alert_email TEXT,
            created_at TEXT
        )
    ''')
    # Price history table for chart
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity TEXT,
            price REAL,
            recorded_at TEXT
        )
    ''')
    conn.commit()
    # Seed some price history data if empty
    count = c.execute('SELECT COUNT(*) FROM price_history').fetchone()[0]
    if count == 0:
        seed_price_history(c)
        conn.commit()
    conn.close()

def seed_price_history(c):
    """Seed realistic price history for the last 12 months"""
    import random
    commodities = [
        ('LPG Cylinder', 800, 950),
        ('Petrol/Diesel', 95, 108),
        ('Edible Oil', 130, 165),
        ('Wheat/Flour', 2000, 2500),
    ]
    base_date = datetime.datetime.now() - datetime.timedelta(days=365)
    for i in range(12):
        record_date = base_date + datetime.timedelta(days=i*30)
        for name, low, high in commodities:
            price = round(random.uniform(low, high), 2)
            c.execute('INSERT INTO price_history (commodity, price, recorded_at) VALUES (?,?,?)',
                      (name, price, record_date.strftime('%Y-%m')))

def save_articles(articles):
    conn = get_conn()
    c = conn.cursor()
    saved = 0
    for a in articles:
        try:
            c.execute('''
                INSERT OR IGNORE INTO articles (title, source, category, severity, link, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (a['title'], a['source'], a['category'], a['severity'],
                  a['link'], datetime.datetime.now().isoformat()))
            if c.rowcount > 0:
                saved += 1
        except Exception:
            continue
    conn.commit()
    conn.close()
    return saved

def get_db_count():
    try:
        conn = get_conn()
        count = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
        conn.close()
        return count
    except:
        return 0

def get_history(limit=50, search=None, category=None, severity=None):
    conn = get_conn()
    query = 'SELECT title, source, category, severity, link, fetched_at FROM articles WHERE 1=1'
    params = []
    if search:
        query += ' AND title LIKE ?'
        params.append(f'%{search}%')
    if category and category != 'all':
        query += ' AND category = ?'
        params.append(category)
    if severity and severity != 'all':
        query += ' AND severity = ?'
        params.append(severity)
    query += ' ORDER BY id DESC LIMIT ?'
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [{'title': r[0], 'source': r[1], 'category': r[2],
             'severity': r[3], 'link': r[4], 'time': r[5][:16] if r[5] else ''} for r in rows]

def get_price_history():
    conn = get_conn()
    rows = conn.execute('''
        SELECT commodity, price, recorded_at FROM price_history
        ORDER BY commodity, recorded_at
    ''').fetchall()
    conn.close()
    result = {}
    for row in rows:
        name = row[0]
        if name not in result:
            result[name] = {'labels': [], 'prices': []}
        result[name]['labels'].append(row[2])
        result[name]['prices'].append(row[1])
    return result

# ── RSS FEEDS ─────────────────────────────────────────────────
FEEDS = [
    {'url': 'https://feeds.bbci.co.uk/news/world/rss.xml',    'source': 'BBC World'},
    {'url': 'https://feeds.bbci.co.uk/news/business/rss.xml', 'source': 'BBC Business'},
    {'url': 'https://reliefweb.int/headlines/rss.xml',         'source': 'ReliefWeb'},
    {'url': 'https://www.thehindu.com/business/Economy/feeder/default.rss', 'source': 'The Hindu'},
]

SAMPLE_NEWS = [
    {'title': 'Iran Launches Drone Strikes — Oil Markets Surge', 'source': 'Reuters', 'category': 'conflict', 'severity': 'critical', 'link': '#', 'time': '1h ago', 'affected': ['LPG Cylinder', 'Petrol / Diesel']},
    {'title': 'OPEC+ Cuts Oil Production — LPG Price Hike Expected in India', 'source': 'BBC Business', 'category': 'energy', 'severity': 'critical', 'link': '#', 'time': '2h ago', 'affected': ['LPG Cylinder', 'Induction Stove']},
    {'title': 'Russia Blocks Ukraine Grain Exports — Wheat Prices Hit 18-Month High', 'source': 'Reuters', 'category': 'economy', 'severity': 'high', 'link': '#', 'time': '3h ago', 'affected': ['Wheat / Flour']},
    {'title': 'Rupee Hits Record Low Against Dollar — Electronics Imports Costlier', 'source': 'The Hindu', 'category': 'economy', 'severity': 'high', 'link': '#', 'time': '4h ago', 'affected': []},
    {'title': 'Cyclone Alert Issued for Tamil Nadu Coast', 'source': 'IMD India', 'category': 'disaster', 'severity': 'high', 'link': '#', 'time': '5h ago', 'affected': []},
    {'title': 'Saudi Arabia Reduces Oil Output — Crude Prices Jump 4%', 'source': 'BBC Business', 'category': 'energy', 'severity': 'high', 'link': '#', 'time': '6h ago', 'affected': ['LPG Cylinder', 'Petrol / Diesel']},
]

def fetch_all_news():
    articles = []
    for feed in FEEDS:
        try:
            d = feedparser.parse(feed['url'])
            for entry in d.entries[:8]:
                title = entry.get('title', '')
                articles.append({
                    'title': title,
                    'source': feed['source'],
                    'link': entry.get('link', '#'),
                    'category': detect_category(title),
                    'severity': classify_severity(title),
                    'time': 'Recently',
                    'affected': get_affected_commodities(title),
                })
        except:
            continue
    if len(articles) < 4:
        return SAMPLE_NEWS
    return articles

# ── EMAIL ALERT ───────────────────────────────────────────────
def send_email_alert(to_email, critical_events):
    """Send email alert for critical events"""
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')

    if not smtp_user or not smtp_pass:
        return False  # Email not configured

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🚨 GeoAlert: {len(critical_events)} Critical Events Detected'
        msg['From'] = smtp_user
        msg['To'] = to_email

        body = f"""
        <html><body style="font-family:sans-serif;background:#080c10;color:#d4e4f7;padding:20px;">
        <h2 style="color:#f5a623;">🌐 GeoAlert — Critical Price Alert</h2>
        <p>{len(critical_events)} critical global events detected that may affect commodity prices in India.</p>
        <hr style="border-color:#1e2d3d;">
        {''.join(f'<div style="background:#0e1419;border-left:3px solid #ff4455;padding:12px;margin:8px 0;border-radius:4px;"><strong>{e["title"]}</strong><br><small style="color:#5a7a99;">{e["source"]} • {e["category"]}</small></div>' for e in critical_events[:5])}
        <p style="color:#5a7a99;font-size:12px;">GeoAlert — Smart Commodity Price Impact Monitor</p>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ── AUTH ROUTES ───────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        alert_email = request.form.get('alert_email', '').strip() or email

        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register.html')

        conn = get_conn()
        try:
            conn.execute('''
                INSERT INTO users (username, email, password_hash, alert_email, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, email, generate_password_hash(password),
                  alert_email, datetime.datetime.now().isoformat()))
            conn.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_conn()
        row = conn.execute('SELECT id, username, email, password_hash, alert_email FROM users WHERE username=?',
                           (username,)).fetchone()
        conn.close()
        if row and check_password_hash(row['password_hash'], password):
            user = User(row['id'], row['username'], row['email'], row['alert_email'])
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        alert_email = request.form.get('alert_email', '').strip()
        conn = get_conn()
        conn.execute('UPDATE users SET alert_email=? WHERE id=?', (alert_email, current_user.id))
        conn.commit()
        conn.close()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')

# ── MAIN ROUTES ───────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/api/news')
@login_required
def api_news():
    news = fetch_all_news()
    saved = save_articles(news)
    # Send email alert if critical events found
    critical = [n for n in news if n['severity'] == 'critical']
    if critical and current_user.alert_email:
        send_email_alert(current_user.alert_email, critical)
    return jsonify(news)

@app.route('/api/news/search')
@login_required
def api_news_search():
    """Search stored articles from DB with keyword + filter support"""
    q = request.args.get('q', '').strip()
    category = request.args.get('category', 'all')
    severity = request.args.get('severity', 'all')
    results = get_history(limit=100, search=q if q else None,
                          category=category if category != 'all' else None,
                          severity=severity if severity != 'all' else None)
    return jsonify(results)

@app.route('/api/commodities')
@login_required
def api_commodities():
    news = fetch_all_news()
    triggered = set(a for item in news for a in item.get('affected', []))
    result = [{**c, 'triggered': c['name'] in triggered} for c in COMMODITY_MAP]
    return jsonify(result)

@app.route('/api/price-history')
@login_required
def api_price_history():
    return jsonify(get_price_history())

@app.route('/api/db-stats')
@login_required
def api_db_stats():
    conn = get_conn()
    total = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
    critical = conn.execute("SELECT COUNT(*) FROM articles WHERE severity='critical'").fetchone()[0]
    conn.close()
    return jsonify({'total': total, 'critical': critical})

@app.route('/api/history')
@login_required
def api_history():
    return jsonify(get_history())

@app.route('/history')
@login_required
def history():
    return render_template('history.html', user=current_user)

# ── MAIN ──────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  GeoAlert v2 is Running!")
    print("  Open: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True)
