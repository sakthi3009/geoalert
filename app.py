from flask import Flask, render_template, jsonify, request
import feedparser
import sqlite3
import datetime
import os

app = Flask(__name__)
DB = 'geoalert.db'

# ── COMMODITY MAP ──────────────────────────────────────────
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

# ── SEVERITY CLASSIFIER ────────────────────────────────────
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

# ── DATABASE ───────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            category TEXT,
            severity TEXT,
            link TEXT,
            fetched_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_articles(articles):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for a in articles:
        c.execute('''
            INSERT INTO articles (title, source, category, severity, link, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (a['title'], a['source'], a['category'], a['severity'],
              a['link'], datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT title, source, category, severity, fetched_at FROM articles ORDER BY id DESC LIMIT 50')
    rows = c.fetchall()
    conn.close()
    return [{'title': r[0], 'source': r[1], 'category': r[2],
             'severity': r[3], 'time': r[4][:16]} for r in rows]

# ── RSS FEEDS ──────────────────────────────────────────────
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
            for entry in d.entries[:6]:
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

# ── ROUTES ─────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/news')
def api_news():
    news = fetch_all_news()
    try:
        save_articles(news)
    except:
        pass
    return jsonify(news)

@app.route('/api/commodities')
def api_commodities():
    news = fetch_all_news()
    triggered = set(a for item in news for a in item.get('affected', []))
    result = []
    for c in COMMODITY_MAP:
        result.append({
            **c,
            'triggered': c['name'] in triggered
        })
    return jsonify(result)

@app.route('/api/history')
def api_history():
    try:
        return jsonify(get_history())
    except:
        return jsonify([])

@app.route('/history')
def history():
    return render_template('history.html')

# ── MAIN ───────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  GeoAlert is Running!")
    print("  Open: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True)
