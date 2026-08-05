import os
import sqlite3
from datetime import datetime
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup
from flask import Flask, jsonify, redirect, request, session, url_for
import requests

# -------------------------------------------------------------
# 🔑 GEMINI API KEY SETUP
# -------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")

try:
  from google import genai

  ai_client = (
      genai.Client(api_key=GEMINI_API_KEY)
      if GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE"
      else None
  )
except ImportError:
  ai_client = None
  print(
      "⚠️ Warning: google-genai module not installed. Run: pip install"
      " google-genai"
  )

app = Flask(__name__)
app.permanent_session_lifetime = 365 * 24 * 60 * 60
app.secret_key = os.environ.get(
    "SECRET_KEY", "bharat_search_permanent_session_key_2026"
)

# Render Persistent Storage support
DB_PATH = os.environ.get("DB_PATH", "search_engine.db")

db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
  os.makedirs(db_dir)

# 👑 Owner Credentials
OWNER_USERNAME = "Aman Giri"
OWNER_PASSWORD = "@Aman2007"

# 🚫 Safe Search Blocklist
BLOCKED_KEYWORDS = ["porn", "xxx", "sex", "adult", "nsfw", "nude", "hot video"]


def is_safe_query(query):
  query_lower = query.lower()
  for word in BLOCKED_KEYWORDS:
    if word in query_lower:
      return False
  return True


# 🕷️ Advance Web Crawler & Favicon Helper (कभी नहीं हटेगा)
def crawl_website_metadata(url):
  try:
    parsed_url = urlparse(url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(url, headers=headers, timeout=5)

    title = ""
    snippet = ""

    if response.status_code == 200:
      soup = BeautifulSoup(response.text, "html.parser")
      if soup.title and soup.title.string:
        title = soup.title.string.strip()
      meta_desc = soup.find(
          "meta", attrs={"name": "description"}
      ) or soup.find("meta", attrs={"property": "og:description"})
      if meta_desc and meta_desc.get("content"):
        snippet = meta_desc["content"].strip()

    if not title:
      title = parsed_url.netloc
    if not snippet:
      snippet = (
          f"Explore {parsed_url.netloc} for official links, features and"
          " updates."
      )

    return title, snippet, favicon_url
  except Exception:
    parsed_url = urlparse(url)
    domain = (
        f"{parsed_url.scheme}://{parsed_url.netloc}"
        if parsed_url.netloc
        else url
    )
    favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    return (
        parsed_url.netloc or url,
        "Instant web result from Bharat Search Engine.",
        favicon_url,
    )


def init_db():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_search_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            snippet TEXT,
            category TEXT,
            logo_url TEXT
        )
    """)

  cursor.execute("PRAGMA table_info(local_search_index)")
  columns = [column[1] for column in cursor.fetchall()]
  if "logo_url" not in columns:
    cursor.execute("ALTER TABLE local_search_index ADD COLUMN logo_url TEXT")

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user'
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            query TEXT,
            timestamp TEXT
        )
    """)

  # 📌 आपकी भेजी गई सभी 1000+ लिंक्स का डेटाबेस जनरेटर
  all_user_items = [
      "Google", "YouTube", "Facebook", "Instagram", "X (Twitter)", "Wikipedia", "Reddit", "Amazon", "Netflix", "LinkedIn", "Yahoo", "Bing", "Microsoft", "Apple", "OpenAI", "WhatsApp Web", "Gmail", "Google Maps", "Google Drive", "Google Translate", "Canva", "Pinterest", "Quora", "TikTok", "Discord", "Twitch", "IMDb", "Stack Overflow", "GitHub", "Medium", "WordPress", "Blogger", "Tumblr", "PayPal", "eBay", "AliExpress", "Flipkart", "Myntra", "Snapdeal", "Spotify", "SoundCloud", "VLC", "Adobe", "Figma", "Notion", "Zoom", "Telegram Web", "Dropbox", "OneDrive", "Mega", "DuckDuckGo", "Brave Search", "Yandex", "Baidu", "Naver", "BBC", "CNN", "The New York Times", "The Guardian", "Reuters", "ESPN", "Cricbuzz", "NDTV", "India Today", "Times of India", "Hindustan Times", "The Hindu", "Moneycontrol", "TradingView", "CoinMarketCap", "Binance", "Coinbase", "Steam", "Epic Games", "Roblox", "Minecraft", "PlayStation", "Xbox", "Nintendo", "EA Sports", "Ubisoft", "Rockstar Games", "Oracle", "IBM", "Intel", "NVIDIA", "AMD", "Samsung", "Xiaomi", "Oppo", "Vivo", "Realme", "Mozilla", "Opera", "Firefox Add-ons", "Chrome Web Store", "Coursera", "Udemy", "Khan Academy", "edX", "W3Schools", "GeeksforGeeks", "MDN Web Docs", "freeCodeCamp", "Codecademy", "HackerRank", "LeetCode", "Codeforces", "CodeChef", "Replit", "Dev.to", "Product Hunt", "TechCrunch", "Ars Technica", "The Verge", "CNET", "Tom's Hardware", "PCMag", "Digital Trends", "Android Authority", "Android Central", "GSMArena", "PhoneArena", "XDA Developers", "Gizmodo", "Mashable", "Lifehacker", "How-To Geek", "ZDNet", "VentureBeat", "Crunchbase", "Indeed", "Glassdoor", "Monster", "Naukri.com", "Internshala", "Upwork", "Fiverr", "Freelancer.com", "Toptal", "Behance", "Dribbble", "DeviantArt", "ArtStation", "Unsplash", "Pexels", "Pixabay", "Shutterstock", "Getty Images", "Freepik", "Envato", "ThemeForest", "CodeCanyon", "Creative Market", "Etsy", "Shopify", "WooCommerce", "Wix", "Squarespace", "Weebly", "Joomla", "Drupal", "Wix Studio", "Google Sites", "Cloudflare", "DigitalOcean", "Vercel", "Netlify", "Heroku", "AWS", "Google Cloud", "Microsoft Azure", "Oracle Cloud", "Alibaba Cloud", "Docker", "Kubernetes", "Jenkins", "GitLab", "Bitbucket", "SourceForge", "Archive.org", "Project Gutenberg", "Google Books", "Open Library", "Wikibooks", "Goodreads", "Scribd", "Wattpad", "Webnovel", "Royal Road", "FanFiction.net", "AO3 (Archive of Our Own)", "JSTOR", "PubMed", "arXiv", "Springer", "ScienceDirect", "Nature", "IEEE Xplore", "ResearchGate", "Academia.edu", "Semantic Scholar", "DOAJ (Directory of Open Access Journals)", "SSRN", "bioRxiv", "medRxiv", "Crossref", "Zenodo", "Figshare", "Mendeley", "Zotero", "EndNote", "ResearchSquare", "Scopus", "Web of Science", "Wolfram Alpha", "MIT OpenCourseWare", "OpenLearn", "FutureLearn", "Alison", "Skillshare", "Pluralsight", "DataCamp", "SoloLearn", "Brilliant", "Codecademy Docs", "Exercism", "Kaggle", "Hugging Face", "Papers with Code", "TensorFlow", "PyTorch", "OpenCV", "Anaconda", "Python.org", "Java.com", "Node.js", "npm", "Rust Lang", "Go.dev", "PHP.net", "Ruby Lang", "Perl.org", "Lua.org", "Kotlin Lang", "Swift.org", "Dart.dev", "Flutter.dev", "Unity", "Unreal Engine", "Godot Engine", "Blender", "Sketchfab", "TurboSquid", "CGTrader", "Poly Haven", "Mixamo", "SketchUp", "AutoCAD Web", "Autodesk", "Tinkercad", "Onshape", "GrabCAD", "Thingiverse", "Printables", "Cults3D", "MyMiniFactory", "Instructables", "Hackster.io", "Arduino", "Raspberry Pi", "Adafruit", "SparkFun", "DigiKey", "Mouser Electronics", "RS Components", "Element14", "All About Circuits", "Electronics Hub", "Circuit Digest", "CircuitLab", "EasyEDA", "KiCad", "Altium", "Proteus Design Suite", "NI (National Instruments)", "MATLAB", "Octave", "Scilab", "Desmos", "GeoGebra", "Symbolab", "Photomath", "Mathway", "Khan Academy Math", "Purplemath", "Paul's Online Math Notes", "CK-12 Foundation", "BYJU'S", "Toppr", "Vedantu", "Unacademy", "Physics Wallah", "Testbook", "Adda247", "BYJU'S Exam Prep", "Embibe", "Doubtnut", "Topcoder", "HackerEarth", "Codewars", "InterviewBit", "AlgoExpert", "Educative", "Coursera for Business", "LinkedIn Learning", "Udacity", "MasterClass", "edureka!", "Simplilearn", "Great Learning", "Intellipaat", "Oracle Learning", "Cisco Networking Academy", "AWS Skill Builder", "Microsoft Learn", "Google Developers", "Google AI", "Google DeepMind", "OpenAI API Platform", "Anthropic", "Perplexity AI", "Stability AI", "Midjourney", "Runway", "ElevenLabs", "Character.AI", "Poe", "Leonardo AI", "Gamma", "Tome", "Zapier", "IFTTT", "Airtable", "Monday.com", "Asana", "Trello", "ClickUp", "Jira", "Confluence", "Slack", "Microsoft Teams", "Google Meet", "Cisco Webex", "Calendly", "Doodle", "Proton Mail", "Zoho Mail", "Outlook", "Yahoo Mail", "Fastmail", "Tutanota", "Proton Drive", "Box", "iCloud", "WeTransfer", "Send Anywhere", "Jumpshare", "TransferNow", "TinyURL", "Bitly", "Linktree", "Carrd", "TinyPNG", "iLovePDF", "Smallpdf", "PDF24 Tools", "PDFescape", "ILoveIMG", "Remove.bg", "Photopea", "Pixlr", "Canva Docs", "VistaCreate", "Kapwing", "VEED.IO", "Clipchamp", "Descript", "Loom", "OBS Project", "Streamlabs", "Restream", "Vimeo", "Dailymotion", "Rumble", "Bilibili", "TED", "National Geographic", "NASA", "European Space Agency (ESA)", "SpaceX", "Blue Origin", "ISRO", "NOAA", "USGS", "World Health Organization (WHO)", "UNICEF", "UNESCO", "United Nations (UN)", "World Bank", "International Monetary Fund (IMF)", "World Economic Forum", "OECD", "European Union", "White House", "European Commission", "NASA Earth Observatory", "National Geographic Kids", "Britannica", "Encyclopedia.com", "Wiktionary", "Wikisource", "Wikimedia Commons", "Wikidata", "Archive Today", "Library of Congress", "British Library", "Europeana", "Smithsonian Institution", "The Metropolitan Museum of Art", "The Louvre", "The British Museum", "Google Arts & Culture", "MoMA (Museum of Modern Art)", "Getty Museum", "National Gallery (UK)", "Rijksmuseum", "Uffizi Galleries", "Vatican Museums", "Metropolitan Opera", "Spotify for Artists", "Apple Music", "Deezer", "Pandora", "TuneIn", "iHeartRadio", "Last.fm", "Genius", "Musixmatch", "Bandcamp", "SoundClick", "Jamendo", "Audiomack", "ReverbNation", "Discogs", "AllMusic", "Rolling Stone", "Billboard", "Pitchfork", "NME", "Rotten Tomatoes", "Metacritic", "Letterboxd", "Fandango", "JustWatch", "Plex", "Jellyfin", "Kodi", "Trakt", "TV Time", "AniList", "MyAnimeList", "Crunchyroll", "HIDIVE", "Viki", "Bilibili Comics", "Webtoon", "Tapas", "MangaDex", "Comic Vine", "Marvel", "DC Comics", "Disney", "Pixar", "DreamWorks", "Warner Bros.", "Universal Pictures", "Paramount Pictures", "Sony Pictures", "Lionsgate", "A24", "IGN", "GameSpot", "PC Gamer", "Eurogamer", "Kotaku", "Polygon", "GameFAQs", "Nexus Mods", "Mod DB", "CurseForge", "Planet Minecraft", "Minecraft Forum", "GTA5-Mods.com", "Speedrun.com", "Chess.com", "Lichess", "FIDE", "ESPN Cricinfo", "Cricbuzz", "ICC Cricket", "FIFA", "UEFA", "NBA", "NFL", "MLB", "NHL", "Formula 1", "MotoGP", "ATP Tour", "WTA Tennis", "Olympics", "World Athletics", "BWF (Badminton)", "FIBA Basketball", "UEFA Champions League", "Premier League", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "IPLT20", "BCCI", "ECB Cricket", "Cricket Australia", "Travel + Leisure", "TripAdvisor", "Booking.com", "Airbnb", "Expedia", "Agoda", "Skyscanner", "Kayak", "Trivago", "MakeMyTrip", "Goibibo", "Yatra", "Cleartrip", "IRCTC", "Uber", "Ola Cabs", "Lyft", "Grab", "Bolt", "BlaBlaCar", "Rome2Rio", "Google Flights", "FlightAware", "Flightradar24", "AccuWeather", "The Weather Channel", "Weather Underground", "Windy", "Time and Date", "XE Currency", "OANDA", "Wise", "Payoneer", "Stripe", "Razorpay", "Paytm", "PhonePe", "BHIM UPI", "Google Pay", "Amazon Pay", "CRED", "Zerodha", "Groww", "Upstox", "Angel One", "ICICI Direct", "HDFC Bank", "SBI", "Axis Bank", "Kotak Mahindra Bank", "Punjab National Bank", "Bank of Baroda", "Canara Bank", "Union Bank of India", "Indian Bank", "IDFC FIRST Bank", "IndusInd Bank", "Yes Bank", "AU Small Finance Bank", "Federal Bank", "WhatsApp", "WhatsApp Business", "Telegram", "Signal", "Messenger", "Facebook Lite", "Threads", "Snapchat", "Skype", "Google Chrome", "Mozilla Firefox", "Microsoft Edge", "Opera Browser", "Brave Browser", "DuckDuckGo Browser", "Waze", "Google Earth", "inDrive", "Rapido", "Files by Google", "Google Photos", "Google Lens", "Google Keep", "Google Calendar", "Google Tasks", "Calculator", "Clock", "YouTube Music", "YouTube Studio", "Disney+", "JioHotstar", "Sony LIV", "ZEE5", "MX Player", "Amazon Music", "Gaana", "JioSaavn", "Wynk Music", "Shazam", "Adobe Express", "Adobe Acrobat Reader", "Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint", "WPS Office", "CamScanner", "Adobe Scan", "Evernote", "Todoist", "Claude", "DeepSeek", "Pi AI", "Grammarly", "LanguageTool", "QuillBot", "Meesho", "AJIO", "Nykaa", "Blinkit", "Swiggy", "Zomato", "BigBasket", "RazorpayX", "Zerodha Kite", "ICICI Direct Markets", "HDFC Sky", "CoinDCX", "CoinSwitch", "WazirX", "Google News", "Microsoft Start", "Feedly", "Inshorts", "Dailyhunt", "Flipboard", "Pocket", "Duolingo", "Memrise", "Busuu", "HelloTalk", "Cake", "Babbel", "Microsoft Math Solver", "WolframAlpha", "Brainly", "Google Classroom", "Microsoft OneNote", "Notability", "Squid", "Xodo PDF Reader", "Adobe Fill & Sign", "Foxit PDF Editor", "Canva AI", "CapCut", "InShot", "KineMaster", "VN Video Editor", "PowerDirector", "Filmora", "Alight Motion", "PicsArt", "Snapseed", "Lightroom Mobile", "Photoshop Express", "Remini", "B612", "VSCO", "Prisma", "ibis Paint X", "Sketchbook", "Infinite Painter", "PixelLab", "Canva Whiteboards", "ChatOn AI", "Grammarly Keyboard", "Gboard", "Microsoft SwiftKey", "Truecaller", "Microsoft Authenticator", "Google Authenticator", "LastPass", "Bitwarden", "NordVPN", "Proton VPN", "Surfshark", "ExpressVPN", "Avast Mobile Security", "Bitdefender Mobile Security", "Malwarebytes", "CCleaner", "SD Maid SE", "CPU-Z", "AIDA64", "CPU Monitor", "DevCheck", "AccuBattery", "Device Info HW", "Greenify", "AirDroid", "TeamViewer", "AnyDesk", "Chrome Remote Desktop", "Microsoft Remote Desktop", "Mi Home", "Google Home", "Amazon Alexa", "SmartThings", "Philips Hue", "TP-Link Tapo", "Kasa Smart", "Home Assistant", "Tasker", "Automate", "MacroDroid", "NFC Tools", "QR & Barcode Scanner", "Google Wallet", "Samsung Wallet", "Stocard", "Microsoft Lens", "CamCard", "Dropbox Sign", "Zoom Workplace", "GoTo Meeting", "BlueJeans Meetings", "Discord Canary", "Guilded", "Element", "Matrix Messenger", "Session Messenger", "Wire Secure Messenger", "Tinder", "Bumble", "Hinge", "happn", "OkCupid", "TrulyMadly", "Aisle", "Jeevansathi", "Shaadi.com", "Bharat Matrimony", "Amazon Kindle", "Google Play Books", "Moon+ Reader", "ReadEra", "Libby", "Audible", "Storytel", "Pocket FM", "Kuku FM", "Pratilipi", "Manga Plus", "Crunchyroll Manga", "WebComics", "Steam Link", "Xbox Game Pass", "PlayStation App", "PlayStation Remote Play", "Nintendo Switch Online", "Epic Games Store", "PUBG MOBILE", "BGMI", "Free Fire MAX", "Call of Duty: Mobile", "Clash of Clans", "Clash Royale", "Brawl Stars", "Clash Mini", "Hay Day", "Boom Beach", "Subway Surfers", "Temple Run 2", "Candy Crush Saga", "Candy Crush Soda Saga", "Royal Match", "Gardenscapes", "Homescapes", "Hill Climb Racing 2", "Asphalt 9: Legends", "Real Racing 3", "Asphalt 8: Airborne", "Need for Speed: No Limits", "CarX Drift Racing 2", "CSR Racing 2", "Mario Kart Tour", "Pokémon GO", "Pokémon Unite", "eFootball™", "EA SPORTS FC Mobile", "Dream League Soccer", "Score! Hero", "8 Ball Pool", "Ludo King", "UNO!™", "Stumble Guys", "Among Us", "Fall Guys Mobile Companion", "Genshin Impact", "Honkai: Star Rail", "Zenless Zone Zero", "Wuthering Waves", "Mobile Legends: Bang Bang", "League of Legends: Wild Rift", "Arena of Valor", "Pokémon TCG Live", "Yu-Gi-Oh! Master Duel", "Shadow Fight 4: Arena", "Shadow Fight 3", "Shadow Fight 2", "Mortal Kombat Mobile", "Injustice 2", "Dragon Ball Legends", "Brawlhalla", "Terraria", "Stardew Valley", "Monument Valley", "Monument Valley 2", "Alto's Odyssey", "Alto's Adventure", "LIMBO", "Inside Playdead", "Dead Cells", "Grimvalor", "Minecraft Education", "Toca Life World", "My Talking Tom 2", "My Talking Angela 2", "Pou", "Duolingo ABC", "ABC Kids", "Khan Academy Kids", "PBS KIDS Games", "LEGO Builder", "LEGO Life", "LEGO® DUPLO® WORLD", "YouTube Kids", "Disney+ Kids Mode", "Baby Panda World", "Samsung Health", "Google Fit", "Fitbit", "Garmin Connect", "Zepp Life", "Huawei Health", "Strava", "Nike Run Club", "Adidas Running", "Map My Run", "MyFitnessPal", "Yazio", "Lifesum", "BetterSleep", "Calm", "Headspace", "Insight Timer", "Medito", "Flo", "Clue", "Period Calendar", "Practo", "Apollo 24|7", "Tata 1mg", "PharmEasy", "Netmeds", "HealthifyMe", "Sleep Cycle", "Google Find My Device", "Samsung SmartThings Find", "Find My Kids", "Life360", "Family Link", "Microsoft Family Safety", "Norton 360", "AVG AntiVirus", "Kaspersky", "ESET Mobile Security", "Avira Security", "McAfee Mobile Security", "Avast Antivirus & Security", "Lookout Security & Antivirus", "1Password", "Dashlane Password Manager", "Bitwarden Password Manager", "KeePassDX", "Authy", "Duo Mobile", "Proton Pass", "LastPass Password Manager", "Opera GX Browser", "Kiwi Browser", "Vivaldi Browser", "Tor Browser", "Firefox Focus", "Samsung Internet Browser", "Adobe Lightroom", "Adobe Photoshop Express", "Adobe Premiere Rush", "Lightroom Camera", "PhotoRoom", "PhotoDirector", "Bazaart", "Mojo", "GoDaddy Studio", "VivaCut", "YouCut", "Motion Ninja", "LumaFusion", "Xodo PDF Reader & Editor", "OfficeSuite", "Polaris Office", "Microsoft 365", "Google Sheets", "Google Slides", "Zoho Writer", "Zoho Sheet", "Zoho Show", "Obsidian", "Joplin", "Simplenote", "TickTick", "Any.do", "Microsoft To Do", "Habitica", "Focus To-Do", "Pomofocus", "Clockify", "Toggl Track", "RescueTime", "Jira Cloud", "Confluence Cloud", "Grammarly Keyboard", "SwiftKey Keyboard", "Fleksy Keyboard", "Chrooma Keyboard", "GO Keyboard", "Facemoji Keyboard", "Typewise Keyboard", "AnySoftKeyboard", "Grok", "LanguageTool", "QuillBot", "Genius Scan", "TurboScan", "Scanner Pro", "Notebloc Scanner", "Google Files", "Solid Explorer", "CX File Explorer", "X-plore File Manager", "Total Commander", "MiXplorer", "ES File Explorer", "File Manager Plus", "ZArchiver", "RAR", "WinZip", "WinRAR", "7Zipper", "DiskDigger", "DiskUsage", "AppMgr III", "APKMirror Installer", "APKPure", "Aurora Store", "F-Droid", "Shizuku", "Termux", "Acode", "QuickEdit", "DroidEdit", "Pydroid 3", "Cxxdroid", "Jvdroid", "Dcoder", "GitJournal", "Code Editor", "TrebEdit", "Spck Editor", "Firebase Console", "AWS Console", "Google Admin", "Google Analytics", "Google Ads", "Meta Ads Manager", "TikTok Studio", "Instagram Edits", "Wix Owner", "Etsy Seller", "eBay Seller Hub", "Amazon Seller", "Apna Job Search", "OLX", "Quikr", "Flipkart Seller Hub", "Swiggy Partner", "Zomato Partner", "Uber Driver", "Ola Driver", "Rapido Captain", "Google Opinion Rewards", "CashKaro", "SMS Organizer"
  ]

  for item in all_user_items:
      clean_name = item.strip()
      if not clean_name:
          continue
      
      # URL Generator
      domain_name = clean_name.lower().replace(" ", "").replace("(", "").replace(")", "").replace("+", "").replace(":", "") + ".com"
      url = f"https://www.{domain_name}"
      snippet = f"Explore official details, features and links for {clean_name} on Bharat Search."
      logo_url = f"https://www.google.com/s2/favicons?domain={domain_name}&sz=64"
      
      cursor.execute(
          "INSERT OR IGNORE INTO local_search_index (title, url, snippet, category, logo_url) VALUES (?, ?, ?, ?, ?)",
          (clean_name, url, snippet, "web", logo_url),
      )

  conn.commit()
  conn.close()


init_db()

HTML_HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bharat AI Search Engine</title>
    <link rel="manifest" href="/manifest.json">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <meta name="theme-color" content="#1a73e8">
    <style>
        html, body { height: 100%; margin: 0; background: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; touch-action: manipulation; }
        body { padding-bottom: 75px; }
        .top-bar-chrome { display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; background: #ffffff; }
        .creator-badge { font-size: 13px; font-weight: 600; color: #5f6368; }
        .top-right-actions { display: flex; align-items: center; gap: 8px; }
        .dots-btn, .account-btn { background: none; border: none; font-size: 22px; color: #444746; cursor: pointer; padding: 4px 8px; border-radius: 50%; display: flex; align-items: center; justify-content: center; text-decoration: none; }
        .dots-btn:hover, .account-btn:hover { background: #f1f3f4; color: #1a73e8; }
        .chrome-menu { border-radius: 20px 0 0 20px; width: 280px !important; }
        .chrome-menu-item { display: flex; align-items: center; gap: 16px; padding: 12px 16px; font-size: 15px; color: #1f1f1f; text-decoration: none; border-radius: 12px; font-weight: 400; }
        .chrome-menu-item:hover { background: #f0f4f9; }
        .chrome-menu-item i { font-size: 18px; color: #444746; }
        .chrome-divider { height: 1px; background: #e0e4e9; margin: 8px 0; }
        .bharat-logo { font-size: 52px; font-weight: 700; letter-spacing: -1.5px; margin-top: 20px; }
        .google-search-container { max-width: 580px; width: 92%; margin: 24px auto 16px auto; position: relative; }
        .google-input { height: 54px; border-radius: 27px; padding-left: 52px; padding-right: 52px; border: 1px solid #dfe1e5; background: #ffffff; box-shadow: 0 1px 6px rgba(32,33,36,0.12); font-size: 16px; }
        .google-input:focus { outline: none; border-color: #4285f4; box-shadow: 0 2px 8px rgba(32,33,36,0.2); }
        .search-left-icon { position: absolute; left: 18px; top: 17px; color: #9aa0a6; font-size: 18px; }
        .mic-btn { position: absolute; right: 18px; top: 15px; background: none; border: none; color: #4285f4; font-size: 20px; cursor: pointer; }
        
        .search-filters { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; border-bottom: 1px solid #e0e0e0; margin-bottom: 16px; }
        .filter-chip { padding: 6px 16px; border-radius: 20px; background: #f1f3f4; color: #3c4043; text-decoration: none; font-size: 14px; white-space: nowrap; font-weight: 500; display: flex; align-items: center; gap: 6px; }
        .filter-chip.active { background: #e8f0fe; color: #1967d2; border: 1px solid #d2e3fc; }
        
        .results-wrapper { max-width: 650px; margin: 0 auto; padding: 0 15px; }
        .result-card { margin-bottom: 24px; }
        .site-logo { width: 18px; height: 18px; object-fit: contain; }
        .result-title { font-size: 19px; color: #1a0dab; font-weight: 600; text-decoration: none; }
        .result-title:hover { text-decoration: underline; }
        .result-snippet { font-size: 14px; color: #4d5156; line-height: 1.5; }

        .suggestions-dropdown {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #ffffff;
            border: 1px solid #dfe1e5;
            border-radius: 0 0 24px 24px;
            box-shadow: 0 4px 6px rgba(32,33,36,0.28);
            z-index: 1000;
            overflow: hidden;
            display: none;
            margin-top: -8px;
        }
        .suggestion-item {
            padding: 10px 20px;
            cursor: pointer;
            font-size: 14px;
            color: #212529;
            text-align: left;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .suggestion-item:hover { background-color: #f8f9fa; }

        .bottom-nav-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #ffffff; border-top: 1px solid #dadce0; display: flex; justify-content: space-around; padding: 8px 0; z-index: 9999; transition: opacity 0.2s ease-in-out, visibility 0.2s ease-in-out; }
        .nav-link-item { text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; display: flex; flex-direction: column; align-items: center; flex: 1; }
        .nav-link-item i { font-size: 20px; margin-bottom: 2px; }
        .nav-link-item.active { color: #1a73e8; font-weight: 600; }
        .nav-hidden { display: none !important; opacity: 0; visibility: hidden; }
    </style>
</head>
<body>
"""


def get_footer(active_tab="home"):
  return f"""
<div class="bottom-nav-bar" id="bottomNav">
    <a href="/" class="nav-link-item {'active' if active_tab == 'home' else ''}"><i class="bi bi-house-door-fill"></i>Home</a>
    <a href="javascript:void(0)" onclick="triggerSearchFocus()" class="nav-link-item {'active' if active_tab == 'search' else ''}"><i class="bi bi-search"></i>Search</a>
    <a href="/games" class="nav-link-item {'active' if active_tab == 'games' else ''}"><i class="bi bi-controller"></i>Games</a>
    <a href="/my_history" class="nav-link-item {'active' if active_tab == 'history' else ''}"><i class="bi bi-clock-history"></i>History</a>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
function startVoiceSearch() {{
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'hi-IN';
    recognition.onresult = function(event) {{
        document.getElementById('searchInput').value = event.results[0][0].transcript;
        document.getElementById('searchForm').submit();
    }};
    recognition.start();
}}

function triggerSearchFocus() {{
    const input = document.getElementById('searchInput');
    if (input) {{ input.focus(); }} else {{ window.location.href = "/?focus=1"; }}
}}

document.addEventListener("DOMContentLoaded", function() {{
    const input = document.getElementById('searchInput');
    const box = document.getElementById('suggestionsBox');

    if (input && box) {{
        input.addEventListener('input', async function() {{
            const val = this.value.trim();
            if (val.length < 2) {{
                box.style.display = 'none';
                return;
            }}

            try {{
                const res = await fetch(`/suggest?q=${{encodeURIComponent(val)}}`);
                const data = await res.json();

                if (data.length > 0) {{
                    box.innerHTML = data.map(item => 
                        `<div class="suggestion-item" onclick="selectSuggestion('${{item.replace(/'/g, "\\'")}}')">
                            <i class="bi bi-search text-muted"></i> ${{item}}
                        </div>`
                    ).join('');
                    box.style.display = 'block';
                }} else {{
                    box.style.display = 'none';
                }}
            }} catch(e) {{
                box.style.display = 'none';
            }}
        }});
    }}
}});

function selectSuggestion(val) {{
    const input = document.getElementById('searchInput');
    if (input) {{
        input.value = val;
        document.getElementById('searchForm').submit();
    }}
}}

const bottomNav = document.getElementById('bottomNav');
if (window.visualViewport) {{
    const initialHeight = window.visualViewport.height;
    window.visualViewport.addEventListener('resize', () => {{
        if (window.visualViewport.height < initialHeight - 120) {{
            bottomNav.classList.add('nav-hidden');
        }} else {{
            bottomNav.classList.remove('nav-hidden');
        }}
    }});
}}

if ('serviceWorker' in navigator) {{
  window.addEventListener('load', () => {{
    navigator.serviceWorker.register('/sw.js').then(() => {{
      console.log('Service Worker Registered Successfully!');
    }}).catch(err => console.log('SW registration failed: ', err));
  }});
}}
</script>
</body>
</html>
"""


@app.route("/manifest.json")
def manifest():
  return jsonify({
      "short_name": "Bharat AI",
      "name": "Bharat AI Search Engine",
      "icons": [{
          "src": (
              "https://cdn-icons-png.flaticon.com/512/1006/1006771.png"
          ),
          "type": "image/png",
          "sizes": "512x512",
      }],
      "start_url": "/",
      "background_color": "#ffffff",
      "theme_color": "#1a73e8",
      "display": "standalone",
  })


@app.route("/sw.js")
def service_worker():
  js = """
    self.addEventListener('install', (e) => {
      self.skipWaiting();
    });
    self.addEventListener('fetch', (event) => {
      event.respondWith(fetch(event.request));
    });
    """
  return js, 200, {"Content-Type": "application/javascript"}


@app.route("/suggest")
def suggest():
  query = request.args.get("q", "").strip()
  if not query or len(query) < 2:
    return jsonify([])

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT DISTINCT title FROM local_search_index WHERE title LIKE ? LIMIT"
      " 5",
      (f"%{query}%",),
  )
  results = cursor.fetchall()
  conn.close()

  suggestions = [row[0] for row in results]
  return jsonify(suggestions)


@app.route("/")
def home():
  user_logged = session.get("user_logged")
  owner_logged = session.get("owner_logged")
  username = session.get("username", "")

  account_url = "/account" if (user_logged or owner_logged) else "/user_login"
  user_info = (
      f'<div class="px-3 py-2 mb-2 text-primary bg-light rounded-3 small">👤'
      f" <b>{username}</b></div>"
      if user_logged
      else ""
  )
  login_logout = (
      '<a href="/confirm_logout?type=user" class="chrome-menu-item'
      ' text-danger"><i class="bi bi-box-arrow-right"></i>Logout</a>'
      if user_logged
      else (
          '<a href="/user_login" class="chrome-menu-item"><i class="bi'
          ' bi-box-arrow-in-right"></i>User Login</a>'
      )
  )

  role_options = ""
  if owner_logged:
    role_options += (
        '<a href="/owner_dashboard" class="chrome-menu-item text-warning"><i'
        ' class="bi bi-crown-fill"></i> Owner Dashboard</a>'
    )
    role_options += (
        '<a href="/confirm_logout?type=owner" class="chrome-menu-item'
        ' text-danger"><i class="bi bi-box-arrow-left"></i> Owner Logout</a>'
    )
  else:
    if not user_logged:
      role_options += (
          '<a href="/owner_login" class="chrome-menu-item"><i class="bi'
          ' bi-shield-lock-fill"></i> Owner Login</a>'
      )

  top_bar = f"""
    <div class="top-bar-chrome">
        <div class="creator-badge">🚀 Created by <b>Aman Giri</b></div>
        <div class="top-right-actions">
            <a href="{account_url}" class="account-btn" title="Account">
                <i class="bi bi-person-circle" style="color: {'#1a73e8' if (user_logged or owner_logged) else '#444746'};"></i>
            </a>
            <button class="dots-btn" type="button" data-bs-toggle="offcanvas" data-bs-target="#chromeMenu">
                <i class="bi bi-three-dots-vertical"></i>
            </button>
        </div>
    </div>
    <div class="offcanvas offcanvas-end chrome-menu p-2" tabindex="-1" id="chromeMenu">
        <div class="offcanvas-body p-2">
            {user_info}
            <a href="/" class="chrome-menu-item"><i class="bi bi-plus-square"></i> New tab</a>
            <a href="{account_url}" class="chrome-menu-item"><i class="bi bi-person-circle"></i> My Account</a>
            <a href="/games" class="chrome-menu-item"><i class="bi bi-controller"></i> Play Milkha Runner</a>
            <a href="/my_history" class="chrome-menu-item"><i class="bi bi-clock-history"></i> History</a>
            <div class="chrome-divider"></div>
            {login_logout}
            {role_options}
        </div>
    </div>
    """

  return (
      HTML_HEADER
      + top_bar
      + f"""
    <div class="container text-center">
        <div class="bharat-logo mb-1">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted small mb-3">India's Automatic AI Search Engine 🇮🇳</p>

        <form action="/search" method="GET" id="searchForm" class="google-search-container">
            <i class="bi bi-search search-left-icon"></i>
            <input type="text" name="q" id="searchInput" class="form-control google-input" placeholder="Poochhein AI se ya search karein web..." required autocomplete="off">
            <button type="button" onclick="startVoiceSearch()" class="mic-btn" title="Search by Voice"><i class="bi bi-mic-fill"></i></button>
            <div id="suggestionsBox" class="suggestions-dropdown"></div>
        </form>
    </div>
    """
      + get_footer("home")
  )


@app.route("/search")
def search():
  query = request.args.get("q", "").strip()
  category = request.args.get("cat", "all").strip().lower()

  if not query:
    return redirect("/")

  if not is_safe_query(query):
    return (
        HTML_HEADER
        + f"""
        <div class="results-wrapper pt-5 text-center">
            <div class="alert alert-danger p-4 shadow-sm">
                <h5>🚫 Safe Search Active</h5>
                <p class="small">Aapki search query Bharat Safety Policy ke khilaf hai.</p>
                <a href="/" class="btn btn-primary btn-sm mt-3">Back to Home</a>
            </div>
        </div>
        """
        + get_footer("search")
    )

  if session.get("user_logged"):
    current_user = session.get("username")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO search_history (username, query, timestamp) VALUES (?,"
        " ?, ?)",
        (current_user, query, current_time),
    )
    conn.commit()
    conn.close()

  ai_response_html = ""
  if category in ["all", "ai"]:
    if ai_client:
      try:
        ai_prompt = f"""
                User Question/Query: "{query}"
                Provide a crisp, accurate, and easy-to-read answer in short (Hinglish/Hindi). 
                Format it nicely with bullet points if explaining steps.
                """
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=ai_prompt,
        )
        ai_text = response.text if response and response.text else ""
        if ai_text:
          ai_response_html = f"""
                    <div class="p-3 mb-4 rounded-4 bg-light border border-primary-subtle shadow-sm">
                        <div class="d-flex align-items-center gap-2 mb-2">
                            <i class="bi bi-stars text-primary fs-5"></i>
                            <h6 class="text-primary fw-bold mb-0">Bharat AI Overview</h6>
                        </div>
                        <div class="text-dark small" style="line-height: 1.6; white-space: pre-line;">{ai_text}</div>
                    </div>
                    """
      except Exception as e:
        print(f"AI Generation Error: {e}")
    else:
      ai_response_html = """
            <div class="p-3 mb-3 rounded-4 bg-light border border-warning shadow-sm">
                <p class="small mb-0 text-muted">💡 <b>AI Answer Feature:</b> Render Environment Variables mein <code>GEMINI_API_KEY</code> set karne ke baad automatic AI answers start ho jayenge.</p>
            </div>
            """

  chips = f"""
    <div class="search-filters">
        <a href="/search?q={query}&cat=all" class="filter-chip {'active' if category == 'all' else ''}"><i class="bi bi-search"></i> All</a>
        <a href="/search?q={query}&cat=ai" class="filter-chip {'active' if category == 'ai' else ''}"><i class="bi bi-stars"></i> AI Mode</a>
        <a href="/search?q={query}&cat=images" class="filter-chip {'active' if category == 'images' else ''}"><i class="bi bi-image"></i> Images</a>
        <a href="/search?q={query}&cat=videos" class="filter-chip {'active' if category == 'videos' else ''}"><i class="bi bi-play-btn"></i> Videos</a>
        <a href="/search?q={query}&cat=apps" class="filter-chip {'active' if category == 'apps' else ''}"><i class="bi bi-phone"></i> Apps</a>
        <a href="/search?q={query}&cat=books" class="filter-chip {'active' if category == 'books' else ''}"><i class="bi bi-book"></i> Books</a>
    </div>
    """

  header_search = f"""
    <div class="bg-white border-bottom p-3 mb-3">
        <div class="d-flex align-items-center gap-2">
            <a href="/" class="bharat-logo text-decoration-none my-0 me-2" style="font-size: 26px;">
                <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">at</span>
            </a>
            <form action="/search" method="GET" id="searchForm" class="google-search-container my-0 flex-grow-1" style="max-width: 100%;">
                <input type="hidden" name="cat" value="{category}">
                <i class="bi bi-search search-left-icon" style="top:12px;"></i>
                <input type="text" name="q" id="searchInput" value="{query}" class="form-control google-input" style="height: 42px; font-size: 14px;" autocomplete="off">
                <button type="button" onclick="startVoiceSearch()" class="mic-btn" style="top:8px;" title="Search by Voice"><i class="bi bi-mic-fill"></i></button>
                <div id="suggestionsBox" class="suggestions-dropdown"></div>
            </form>
        </div>
    </div>
    <div class="results-wrapper">
        {chips}
        {ai_response_html if category in ['all', 'ai'] else ''}
    """

  body_results = ""

  if category == "images":
    encoded_q = quote_plus(query)
    body_results += f"""
        <div class="row g-2">
            <div class="col-6 col-md-4">
                <a href="https://www.google.com/search?tbm=isch&q={encoded_q}" target="_blank" class="card text-decoration-none shadow-sm border-0">
                    <img src="https://picsum.photos/300/200?random=1" class="card-img-top rounded-3" alt="Image">
                    <div class="card-body p-2 text-center"><span class="small text-dark fw-bold">{query} 1</span></div>
                </a>
            </div>
            <div class="col-6 col-md-4">
                <a href="https://www.google.com/search?tbm=isch&q={encoded_q}" target="_blank" class="card text-decoration-none shadow-sm border-0">
                    <img src="https://picsum.photos/300/200?random=2" class="card-img-top rounded-3" alt="Image">
                    <div class="card-body p-2 text-center"><span class="small text-dark fw-bold">{query} 2</span></div>
                </a>
            </div>
        </div>
        """

  elif category == "videos":
    encoded_q = quote_plus(query)
    body_results += f"""
        <div class="d-flex flex-column gap-3">
            <div class="p-3 border rounded-3 bg-light d-flex align-items-center gap-3">
                <i class="bi bi-youtube text-danger display-6"></i>
                <div>
                    <h6 class="mb-1"><a href="https://www.youtube.com/results?search_query={encoded_q}" target="_blank" class="text-decoration-none text-dark fw-bold">Watch '{query}' on YouTube</a></h6>
                    <p class="small text-muted mb-0">Search videos & tutorials on YouTube.</p>
                </div>
            </div>
        </div>
        """

  else:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if category == "all":
      cursor.execute(
          "SELECT title, url, snippet, category, logo_url FROM"
          " local_search_index WHERE title LIKE ? OR snippet LIKE ?",
          (f"%{query}%", f"%{query}%"),
      )
    else:
      cursor.execute(
          "SELECT title, url, snippet, category, logo_url FROM"
          " local_search_index WHERE category = ? AND (title LIKE ? OR snippet"
          " LIKE ?)",
          (category, f"%{query}%", f"%{query}%"),
      )
    rows = cursor.fetchall()
    conn.close()

    if rows:
      for row in rows:
        title, url, snippet, cat, logo_url = (
            row[0],
            row[1],
            row[2],
            row[3].upper(),
            row[4],
        )
        parsed = urlparse(url)
        domain_name = parsed.netloc if parsed.netloc else url

        if not logo_url:
          logo_url = (
              f"https://www.google.com/s2/favicons?domain={domain_name}&sz=64"
          )

        body_results += f"""
                <div class="result-card mb-4 pb-2 border-bottom">
                    <div class="d-flex align-items-center gap-2 mb-1">
                        <div class="bg-light rounded-circle d-flex align-items-center justify-content-center border" style="width:28px; height:28px; overflow:hidden;">
                            <img src="{logo_url}" class="site-logo" alt="Logo" onerror="this.src='https://cdn-icons-png.flaticon.com/512/1006/1006771.png'">
                        </div>
                        <div class="d-flex flex-column" style="line-height: 1.2;">
                            <span class="fw-medium text-dark" style="font-size: 14px;">{domain_name}</span>
                            <span class="text-muted" style="font-size: 12px; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{url}</span>
                        </div>
                        <i class="bi bi-three-dots-vertical ms-auto text-muted small"></i>
                    </div>

                    <a href="{url}" target="_blank" class="result-title">
                        {title}
                    </a>

                    <div class="result-snippet mt-1">
                        {snippet}
                    </div>
                </div>
                """
    elif category != "ai":
      body_results += f"""
            <div class="text-center text-muted p-4 bg-light rounded-4 border">
                <h6>No indexed pages found for "{query}".</h6>
                <p class="small text-muted mb-0">Owner Dashboard se link add karein!</p>
            </div>
            """

  body_results += "</div>"
  return HTML_HEADER + header_search + body_results + get_footer("search")


@app.route("/account")
def account():
  user_logged = session.get("user_logged")
  owner_logged = session.get("owner_logged")
  username = session.get("username", "")

  if not user_logged and not owner_logged:
    return redirect("/user_login")

  role_title = "👑 Owner" if owner_logged else "👤 User"
  display_name = OWNER_USERNAME if owner_logged else username

  return (
      HTML_HEADER
      + f"""
    <div class="container mt-4 mb-5" style="max-width: 500px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <div class="display-4 mb-2">👤</div>
            <h4>{display_name}</h4>
            <span class="badge bg-primary mb-3">{role_title}</span>
            <hr>
            <div class="d-grid gap-2 mt-4">
                <a href="/my_history" class="btn btn-outline-secondary"><i class="bi bi-clock-history"></i> Search History</a>
                {'<a href="/owner_dashboard" class="btn btn-warning"><i class="bi bi-crown-fill"></i> Owner Dashboard</a>' if owner_logged else ''}
                <a href="/confirm_logout?type={'owner' if owner_logged else 'user'}" class="btn btn-danger"><i class="bi bi-box-arrow-right"></i> Logout</a>
            </div>
        </div>
    </div>
    """
      + get_footer("home")
  )


@app.route("/games")
def games():
  return (
      HTML_HEADER
      + """
    <div class="container text-center mt-3" style="max-width: 500px;">
        <h4 class="mb-1 text-primary fw-bold">🏃 Milkha Singh: Flying Sikh Run</h4>
        <p class="text-muted small mb-2">Hurdles (🧱) se bachein aur Energy Milk (🥛) collect karein!</p>
        <div class="bg-white p-3 rounded-4 shadow-sm border position-relative">
            <canvas id="runnerCanvas" width="320" height="200" style="background: linear-gradient(to bottom, #87CEEB 70%, #d2b48c 70%); border-radius:12px; border:2px solid #ccc;"></canvas>
            <div class="d-flex justify-content-between align-items-center mt-3 px-2">
                <button class="btn btn-warning btn-lg fw-bold w-100 py-3 shadow-sm" onclick="jump()" style="border-radius: 15px;">🚀 JUMP (TAP / SPACE)</button>
            </div>
        </div>
        <div class="mt-3 mb-4"><a href="/" class="btn btn-outline-secondary btn-sm" style="border-radius: 20px;">Back to Home</a></div>
    </div>
    <script>
        const canvas = document.getElementById("runnerCanvas");
        const ctx = canvas.getContext("2d");
        let milkha = { x: 30, y: 110, width: 25, height: 30, dy: 0, gravity: 0.8, isJumping: false };
        let obstacles = [], milks = [], score = 0, gameFrame = 0, gameOver = false;
        
        function jump() { 
            if (!milkha.isJumping && !gameOver) { 
                milkha.dy = -12; 
                milkha.isJumping = true; 
            } else if (gameOver) { 
                resetGame(); 
            } 
        }
        
        document.addEventListener("keydown", function(e) { 
            if (e.code === "Space" || e.code === "ArrowUp") jump(); 
        });
        
        function resetGame() { 
            milkha.y = 110; milkha.dy = 0; milkha.isJumping = false; 
            obstacles = []; milks = []; score = 0; gameFrame = 0; gameOver = false; 
            loop(); 
        }
        
        function update() {
            if (gameOver) return;
            gameFrame++; milkha.dy += milkha.gravity; milkha.y += milkha.dy;
            if (milkha.y >= 110) { milkha.y = 110; milkha.dy = 0; milkha.isJumping = false; }
            if (gameFrame % 90 === 0) obstacles.push({ x: canvas.width, y: 115, width: 20, height: 25 });
            if (gameFrame % 140 === 0) milks.push({ x: canvas.width, y: 70, width: 20, height: 20 });
            
            for (let i = 0; i < obstacles.length; i++) {
                obstacles[i].x -= 5;
                if (milkha.x < obstacles[i].x + obstacles[i].width && milkha.x + milkha.width > obstacles[i].x && milkha.y < obstacles[i].y + obstacles[i].height && milkha.y + milkha.height > obstacles[i].y) gameOver = true;
            }
            
            for (let i = 0; i < milks.length; i++) {
                milks[i].x -= 5;
                if (milkha.x < milks[i].x + milks[i].width && milkha.x + milkha.width > milks[i].x && milkha.y < milks[i].y + milks[i].height && milkha.y + milkha.height > milks[i].y) { score += 5; milks.splice(i, 1); i--; }
            }
            
            obstacles = obstacles.filter(o => o.x > -20); 
            milks = milks.filter(m => m.x > -20);
            if (gameFrame % 10 === 0) score += 1;
        }
        
        function draw() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = "#8B4513"; ctx.fillRect(0, 140, canvas.width, 60);
            ctx.fillStyle = "#FFF"; ctx.fillRect(0, 142, canvas.width, 3);
            
            ctx.save();
            ctx.translate(milkha.x + milkha.width, milkha.y);
            ctx.scale(-1, 1);
            ctx.font = "26px Arial"; 
            ctx.fillText("🏃", 0, 24);
            ctx.restore();
            
            ctx.font = "22px Arial";
            for (let o of obstacles) ctx.fillText("🧱", o.x, o.y + 20);
            for (let m of milks) ctx.fillText("🥛", m.x, m.y + 18);
            
            ctx.fillStyle = "#000"; ctx.font = "bold 14px Arial"; ctx.fillText("Score: " + score, 10, 20);
            
            if (gameOver) {
                ctx.fillStyle = "rgba(0, 0, 0, 0.75)"; ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = "#FFF"; ctx.font = "bold 20px Arial"; ctx.fillText("GAME OVER!", 90, 90);
                ctx.font = "14px Arial"; ctx.fillText("Final Score: " + score, 110, 115); ctx.fillText("Tap Jump Button to Restart", 70, 145);
            }
        }
        
        function loop() { update(); draw(); if (!gameOver) requestAnimationFrame(loop); }
        loop();
    </script>
    """
      + get_footer("games")
  )


@app.route("/my_history")
def my_history():
  if not session.get("user_logged"):
    return redirect("/user_login")
  current_user = session.get("username")
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT query, timestamp FROM search_history WHERE username = ? ORDER BY"
      " id DESC",
      (current_user,),
  )
  history_list = cursor.fetchall()
  conn.close()

  history_rows = ""
  for h in history_list:
    history_rows += f'<li class="list-group-item d-flex justify-content-between align-items-center"><span>🔍 <b>{h[0]}</b></span><span class="text-muted small">{h[1]}</span></li>'

  return (
      HTML_HEADER
      + f"""
    <div class="container mt-4 mb-5" style="max-width: 600px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">📜 Search History ({current_user})</h4>
            <ul class="list-group list-group-flush mb-3">{history_rows if history_rows else '<li class="list-group-item text-center text-muted">No history found.</li>'}</ul>
            <div class="text-center"><a href="/" class="btn btn-outline-primary btn-sm rounded-pill">Back to Home</a></div>
        </div>
    </div>
    """
      + get_footer("history")
  )


@app.route("/confirm_logout", methods=["GET", "POST"])
def confirm_logout():
  account_type = request.args.get("type", "user")
  error = ""
  if request.method == "POST":
    entered_password = request.form.get("password")
    if account_type == "owner" and entered_password == OWNER_PASSWORD:
      session.pop("owner_logged", None)
      return redirect("/")
    elif account_type == "user":
      current_user = session.get("username")
      conn = sqlite3.connect(DB_PATH)
      cursor = conn.cursor()
      cursor.execute(
          "SELECT * FROM users WHERE username = ? AND password = ?",
          (current_user, entered_password),
      )
      user = cursor.fetchone()
      conn.close()
      if user:
        session.pop("user_logged", None)
        session.pop("username", None)
        return redirect("/")
    error = "Incorrect Password!"

  return (
      HTML_HEADER
      + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-danger">🔒 Security Check</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <input type="password" name="password" class="form-control mb-3" placeholder="Enter Password to Logout" required>
            <button type="submit" class="btn btn-danger w-100 mb-2 rounded-pill">Confirm Logout</button>
            <a href="/" class="btn btn-light w-100 rounded-pill">Cancel</a>
        </form>
    </div>
    """
      + get_footer("home")
  )


@app.route("/owner_login", methods=["GET", "POST"])
def owner_login():
  error = ""
  if request.method == "POST":
    if (
        request.form.get("username") == OWNER_USERNAME
        and request.form.get("password") == OWNER_PASSWORD
    ):
      session.permanent = True
      session["owner_logged"] = True
      return redirect("/owner_dashboard")
    else:
      error = "Invalid Owner Credentials!"
  return (
      HTML_HEADER
      + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-warning">👑 Owner Login</h4>
            {f'<div class="alert alert-danger">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
            <button type="submit" class="btn btn-warning w-100 fw-bold rounded-pill">Login</button>
        </form>
    </div>
    """
      + get_footer("home")
  )


# 👑 🕷️ Owner Dashboard (Smart Web Crawler Option Retained Safely)
@app.route("/owner_dashboard", methods=["GET", "POST"])
def owner_dashboard():
  if not session.get("owner_logged"):
    return redirect("/owner_login")

  message = ""
  if request.method == "POST":
    form_type = request.form.get("form_type")
    if form_type == "add_index":
      url = request.form.get("url", "").strip()
      title = request.form.get("title", "").strip()
      snippet = request.form.get("snippet", "").strip()
      category = request.form.get("category", "web").strip()
      custom_logo = request.form.get("logo_url", "").strip()

      if url:
        c_title, c_snippet, c_logo = crawl_website_metadata(url)
        final_title = title if title else c_title
        final_snippet = snippet if snippet else c_snippet
        final_logo = custom_logo if custom_logo else c_logo

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO local_search_index (title, url, snippet, category,"
            " logo_url) VALUES (?, ?, ?, ?, ?)",
            (final_title, url, final_snippet, category, final_logo),
        )
        conn.commit()
        conn.close()
        message = f"✅ Crawled & Added '{final_title}' successfully!"

    elif form_type == "add_user":
      new_user = request.form.get("username", "").strip()
      new_pass = request.form.get("password", "").strip()
      new_role = request.form.get("role", "user")
      if new_user and new_pass:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
          cursor.execute(
              "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
              (new_user, new_pass, new_role),
          )
          conn.commit()
          message = f"✅ Added user: {new_user}"
        except sqlite3.IntegrityError:
          message = "⚠️ Username already exists!"
        conn.close()

  return (
      HTML_HEADER
      + f"""
    <div class="container mt-4 mb-5" style="max-width: 750px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">👑 Owner Control Center</h4>
            {f'<div class="alert alert-info">{message}</div>' if message else ''}
            
            <!-- Smart Web Crawler Option -->
            <form method="POST" class="border p-3 rounded-3 mb-4 bg-light">
                <input type="hidden" name="form_type" value="add_index">
                <h6 class="text-primary mb-2">🕷️ Smart Web Crawler</h6>
                <div class="row g-2">
                    <div class="col-12"><input type="url" name="url" class="form-control mb-2" placeholder="Website URL (https://...)" required></div>
                    <div class="col-md-6"><input type="text" name="title" class="form-control mb-2" placeholder="Custom Title (Optional)"></div>
                    <div class="col-md-6"><input type="url" name="logo_url" class="form-control mb-2" placeholder="Custom Logo URL (Optional)"></div>
                    <div class="col-md-8"><input type="text" name="snippet" class="form-control mb-2" placeholder="Custom Snippet (Optional)"></div>
                    <div class="col-md-4">
                        <select name="category" class="form-select mb-2">
                            <option value="web">Web</option>
                            <option value="apps">Apps</option>
                            <option value="games">Games</option>
                            <option value="books">Books</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary w-100 mt-2">Crawl & Save</button>
            </form>

            <form method="POST" class="row g-2 border p-3 rounded-3 mb-4">
                <input type="hidden" name="form_type" value="add_user">
                <h6 class="text-success mb-2">➕ Add New User</h6>
                <div class="col-md-4"><input type="text" name="username" class="form-control" placeholder="Username" required></div>
                <div class="col-md-4"><input type="text" name="password" class="form-control" placeholder="Password" required></div>
                <div class="col-md-2"><select name="role" class="form-select"><option value="user">User</option><option value="admin">Admin</option></select></div>
                <div class="col-md-2"><button type="submit" class="btn btn-success w-100">Add</button></div>
            </form>

            <div class="text-center"><a href="/" class="btn btn-outline-secondary btn-sm rounded-pill">Back to Home</a></div>
        </div>
    </div>
    """
      + get_footer("home")
  )


@app.route("/user_login", methods=["GET", "POST"])
def user_login():
  if session.get("user_logged"):
    return redirect("/account")
  error = ""
  if request.method == "POST":
    username = request.form.get("username")
    password = request.form.get("password")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password),
    )
    user = cursor.fetchone()
    conn.close()
    if user:
      session.permanent = True
      session["user_logged"] = True
      session["username"] = username
      return redirect("/account")
    else:
      error = "Invalid Credentials!"
  return (
      HTML_HEADER
      + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">User Login</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
            <button type="submit" class="btn btn-primary w-100 rounded-pill">Login</button>
        </form>
    </div>
    """
      + get_footer("home")
  )


if __name__ == "__main__":
  app.run(debug=True, port=5000)
