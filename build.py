import os
import re
import csv
import json
import html
import shutil
import hashlib
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import quote

# ============================================================
# INTIMACY QUIZ HUB — PRODUCTION STATIC PSEO WEBSITE BUILDER
# Python 3 | Zero Dependencies | Cloudflare Workers / Pages
# ============================================================

BASE_URL = os.environ.get(
    "BASE_URL",
    "https://intimacy-quiz-hub.velvetgrid.workers.dev"
).rstrip("/")

SITE_NAME = "Intimacy Quiz Hub"
NICHE_TOPIC = "Interactive Couples Compatibility Quizzes, Romantic Archetypes & Date Night Tests"
CONTACT_EMAIL = "nancympatten@gmail.com"

AFFILIATE_URL = "#affiliate-link"
AFFILIATE_CTA_TEXT = "Discover Your Ideal AI Companion Match Based on Your Result"

CURRENT_YEAR = datetime.utcnow().year

# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "data.csv"
OUTPUT_DIR = "dist"

ITEMS_PER_PAGE = 24
RELATED_LIMIT = 8
NEWEST_LIMIT = 30
SITEMAP_LIMIT = 45000

SITE_DESCRIPTION = (
    "Explore interactive couples compatibility quizzes, romantic personality "
    "tests, relationship archetypes and fun date-night challenges. "
    "Discover something new about your relationship."
)

COLORS = {
    "background": "#080b0f",
    "surface": "#111722",
    "surface2": "#18212d",
    "rose": "#ec4899",
    "emerald": "#10b981",
    "text": "#f3f4f6",
    "muted": "#9ca3af",
    "border": "#263244",
}

# ============================================================
# UTILITIES
# ============================================================

def esc(value):
    return html.escape(str(value or ""), quote=True)


def slugify(value):
    value = str(value or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "uncategorized"


def safe_json(value):
    return json.dumps(
        value,
        ensure_ascii=False
    ).replace("</", "<\\/")


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_tags(value):
    if not value:
        return []

    if "|" in value:
        parts = value.split("|")
    else:
        parts = value.split(",")

    return list(dict.fromkeys(
        clean_text(x) for x in parts if clean_text(x)
    ))


def parse_date(value):
    value = clean_text(value)

    if not value:
        return datetime.min

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except ValueError:
        return datetime.min


def truncate(value, limit=155):
    value = clean_text(value)

    if len(value) <= limit:
        return value

    return value[:limit].rsplit(" ", 1)[0].rstrip(".,;:") + "..."


def write_file(path, content):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(content)


def canonical(path=""):
    return BASE_URL + ("/" + path.lstrip("/") if path else "/")


def make_link(path, label, css=""):
    return (
        f'<a href="{esc(path)}"'
        + (f' class="{esc(css)}"' if css else "")
        + f'>{esc(label)}</a>'
    )


def normalize_question(question):
    question = clean_text(question)

    if "?" not in question:
        return question, []

    parts = question.split("?", 1)
    title = clean_text(parts[0]) + "?"
    options = [
        clean_text(x)
        for x in parts[1].split(";")
        if clean_text(x)
    ]

    return title, options[:3]


def parse_questions(value):
    questions = []

    for raw in str(value or "").split("|"):
        if not clean_text(raw):
            continue

        title, options = normalize_question(raw)

        if len(options) != 3:
            print(
                f"WARNING: Question must have exactly 3 options: {title}"
            )
            continue

        questions.append({
            "question": title,
            "options": options
        })

    return questions


def parse_results(value):
    return [
        clean_text(x)
        for x in str(value or "").split("|")
        if clean_text(x)
    ]


def valid_external_url(url):
    return str(url).startswith(("https://", "http://"))


# ============================================================
# CSV LOADING AND VALIDATION
# ============================================================

REQUIRED_COLUMNS = [
    "slug",
    "title",
    "category",
    "subcategory",
    "target_keyword",
    "quiz_questions",
    "result_profiles",
    "description",
    "tags",
    "faq_q1",
    "faq_a1",
    "faq_q2",
    "faq_a2",
    "upload_date",
]


def load_data():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Missing {INPUT_FILE}. Place data.csv beside build.py."
        )

    records = []
    seen_slugs = set()

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("data.csv is empty or has no CSV header.")

        missing = [
            col for col in REQUIRED_COLUMNS
            if col not in reader.fieldnames
        ]

        if missing:
            raise ValueError(
                "Missing required CSV columns: " + ", ".join(missing)
            )

        for line_number, row in enumerate(reader, start=2):

            if not row or not any(row.values()):
                continue

            slug = slugify(row.get("slug", ""))

            if slug in seen_slugs:
                raise ValueError(
                    f"Duplicate slug '{slug}' at CSV line {line_number}."
                )

            seen_slugs.add(slug)

            questions = parse_questions(row.get("quiz_questions", ""))
            results = parse_results(row.get("result_profiles", ""))

            if len(questions) != 6:
                print(
                    f"WARNING: {slug} has {len(questions)} valid questions; "
                    "the quiz player will use the available questions."
                )

            if len(results) != 3:
                print(
                    f"WARNING: {slug} has {len(results)} result profiles. "
                    "Missing profiles will use fallback text."
                )

            category = clean_text(row.get("category")) or "General Quizzes"
            subcategory = clean_text(row.get("subcategory")) or "General"

            records.append({
                "slug": slug,
                "title": clean_text(row.get("title")) or slug.replace("-", " ").title(),
                "category": category,
                "category_slug": slugify(category),
                "subcategory": subcategory,
                "subcategory_slug": slugify(subcategory),
                "target_keyword": clean_text(row.get("target_keyword")),
                "quiz_questions": questions,
                "result_profiles": results,
                "description": clean_text(row.get("description")) or SITE_DESCRIPTION,
                "tags": parse_tags(row.get("tags")),
                "faq_q1": clean_text(row.get("faq_q1")),
                "faq_a1": clean_text(row.get("faq_a1")),
                "faq_q2": clean_text(row.get("faq_q2")),
                "faq_a2": clean_text(row.get("faq_a2")),
                "upload_date": clean_text(row.get("upload_date")),
                "date_object": parse_date(row.get("upload_date")),
            })

    if not records:
        raise ValueError("No valid quiz records found in data.csv.")

    return records


# ============================================================
# SHARED CSS
# ============================================================

CSS = r"""
:root {
    color-scheme: dark;
    --bg: #080b0f;
    --card: #111722;
    --card2: #18212d;
    --rose: #ec4899;
    --emerald: #10b981;
    --text: #f3f4f6;
    --muted: #9ca3af;
    --border: #263244;
    --radius: 18px;
}

* { box-sizing: border-box; }

html {
    scroll-behavior: smooth;
    background: var(--bg);
}

body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont,
                 "Segoe UI", sans-serif;
    line-height: 1.7;
    min-height: 100vh;
}

a {
    color: var(--emerald);
    text-decoration: none;
}

a:hover { color: var(--rose); }

button, input { font: inherit; }

button { cursor: pointer; }

.container {
    width: min(1120px, calc(100% - 36px));
    margin: auto;
}

.site-header {
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(8,11,15,.94);
    backdrop-filter: blur(15px);
    border-bottom: 1px solid var(--border);
}

.nav {
    min-height: 72px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
}

.brand {
    color: white;
    font-size: 20px;
    font-weight: 900;
    letter-spacing: -.7px;
}

.brand span { color: var(--rose); }

.nav-links {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    font-size: 13px;
}

.hero {
    padding: 75px 0 55px;
    text-align: center;
}

.eyebrow {
    display: inline-block;
    padding: 6px 13px;
    border: 1px solid rgba(16,185,129,.35);
    background: rgba(16,185,129,.08);
    color: var(--emerald);
    border-radius: 30px;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}

h1, h2, h3 {
    line-height: 1.2;
    letter-spacing: -.6px;
}

h1 {
    font-size: clamp(34px, 6vw, 62px);
    margin: 22px 0;
}

h2 { font-size: clamp(23px, 4vw, 32px); }

.hero p {
    max-width: 720px;
    margin: 0 auto;
    color: var(--muted);
}

.gradient {
    background: linear-gradient(110deg, var(--rose), var(--emerald));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.section { padding: 35px 0; }

.section-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 20px;
}

.section-heading h2 { margin: 0; }

.grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 17px;
}

.card {
    padding: 21px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    transition: transform .2s, border-color .2s;
}

.card:hover {
    transform: translateY(-3px);
    border-color: rgba(236,72,153,.6);
}

.card h3 { margin: 8px 0; font-size: 18px; }

.card p {
    color: var(--muted);
    font-size: 14px;
}

.meta {
    font-size: 12px;
    color: var(--muted);
}

.pill {
    display: inline-block;
    margin: 4px 4px 4px 0;
    padding: 5px 11px;
    background: var(--card2);
    border: 1px solid var(--border);
    border-radius: 30px;
    color: var(--muted);
    font-size: 12px;
}

.pill:hover {
    color: var(--emerald);
    border-color: var(--emerald);
}

.search-box {
    width: 100%;
    padding: 17px 20px;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--card);
    color: white;
    outline: none;
    margin: 22px 0;
}

.search-box:focus { border-color: var(--emerald); }

.btn {
    display: inline-flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    padding: 13px 20px;
    border: 0;
    border-radius: 12px;
    background: linear-gradient(110deg, var(--rose), #db2777);
    color: white;
    font-weight: 800;
    transition: opacity .2s, transform .2s;
}

.btn:hover {
    color: white;
    opacity: .9;
    transform: translateY(-1px);
}

.btn-green {
    background: linear-gradient(110deg, #059669, #10b981);
}

.btn-outline {
    background: transparent;
    border: 1px solid var(--border);
}

.btn:disabled { opacity: .45; cursor: not-allowed; }

.quiz-shell {
    max-width: 780px;
    margin: 30px auto;
    padding: 28px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 22px;
}

.quiz-status {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    font-size: 13px;
    color: var(--muted);
}

.progress-track {
    height: 8px;
    margin: 15px 0 25px;
    background: var(--card2);
    border-radius: 30px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    width: 0;
    background: linear-gradient(90deg, var(--rose), var(--emerald));
    transition: width .3s;
}

.question-title {
    font-size: clamp(20px, 4vw, 27px);
    margin: 20px 0;
}

.option {
    display: block;
    width: 100%;
    text-align: left;
    margin: 12px 0;
    padding: 16px;
    background: var(--card2);
    border: 1px solid var(--border);
    border-radius: 12px;
    color: var(--text);
    transition: .2s;
}

.option:hover {
    border-color: var(--rose);
    background: rgba(236,72,153,.08);
}

.option:focus-visible, .btn:focus-visible {
    outline: 2px solid var(--emerald);
    outline-offset: 3px;
}

.result-box {
    padding: 25px;
    border: 1px solid rgba(16,185,129,.4);
    background: rgba(16,185,129,.055);
    border-radius: 18px;
}

.result-box h2 { color: var(--emerald); }

.affiliate {
    margin-top: 24px;
    padding: 24px;
    background: linear-gradient(135deg, #241426, #10251f);
    border: 1px solid rgba(236,72,153,.35);
    border-radius: 16px;
}

.updated-badge {
    display: inline-block;
    padding: 7px 12px;
    border-radius: 30px;
    background: rgba(16,185,129,.1);
    border: 1px solid rgba(16,185,129,.3);
    color: var(--emerald);
    font-size: 12px;
    font-weight: 800;
}

.breadcrumb {
    padding: 22px 0;
    color: var(--muted);
    font-size: 13px;
}

.content {
    max-width: 850px;
    margin: auto;
    color: #d1d5db;
}

.content h2, .content h3 { color: white; }

.faq-item {
    padding: 18px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin: 12px 0;
}

.faq-item h3 { margin-top: 0; }

.pagination {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
    padding: 35px 0;
}

.site-footer {
    margin-top: 70px;
    padding: 45px 0;
    background: #06090d;
    border-top: 1px solid var(--border);
}

.footer-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 30px;
}

.footer-grid h3 { font-size: 15px; }

.footer-grid a {
    display: block;
    margin: 8px 0;
    font-size: 13px;
    color: var(--muted);
}

.empty-state {
    padding: 35px;
    text-align: center;
    color: var(--muted);
}

.age-overlay {
    position: fixed;
    inset: 0;
    z-index: 9999;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: rgba(0,0,0,.96);
    backdrop-filter: blur(12px);
}

.age-modal {
    width: min(430px, 100%);
    padding: 30px;
    text-align: center;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 20px;
}

.age-modal h2 { color: var(--rose); }

.age-modal p { color: var(--muted); }

.age-actions {
    display: flex;
    gap: 10px;
    justify-content: center;
    flex-wrap: wrap;
}

.hidden { display: none !important; }

@media(max-width: 800px) {
    .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .footer-grid { grid-template-columns: 1fr 1fr; }
}

@media(max-width: 560px) {
    .container { width: calc(100% - 26px); }
    .grid { grid-template-columns: 1fr; }
    .hero { padding: 48px 0 35px; }
    .nav { min-height: 65px; }
    .nav-links { gap: 9px; font-size: 11px; }
    .quiz-shell { padding: 18px; }
    .footer-grid { grid-template-columns: 1fr; }
}
"""

# ============================================================
# GLOBAL JAVASCRIPT
# ============================================================

GLOBAL_JS = r"""
<script>
(function() {
    "use strict";

    function updateLiveContent() {
        const now = new Date();
        const year = now.getFullYear();
        const month = now.toLocaleString(undefined, {month: "long"});

        document.querySelectorAll(".live-year").forEach(function(el) {
            el.textContent = year;
        });

        document.querySelectorAll(".updated-quiz-edition").forEach(function(el) {
            el.textContent = "Updated Quiz Edition • " + month + " " + year;
        });
    }

    updateLiveContent();

    const ageOverlay = document.getElementById("age-overlay");

    if (ageOverlay) {
        let verified = false;

        try {
            verified = localStorage.getItem("iqh_age_verified") === "yes";
        } catch(e) {}

        if (!verified) {
            ageOverlay.style.display = "flex";
        }

        const yes = document.getElementById("age-yes");
        const no = document.getElementById("age-no");

        if (yes) {
            yes.addEventListener("click", function() {
                try {
                    localStorage.setItem("iqh_age_verified", "yes");
                } catch(e) {}

                ageOverlay.style.display = "none";
            });
        }

        if (no) {
            no.addEventListener("click", function() {
                document.body.innerHTML =
                    '<main style="padding:60px;text-align:center;color:white">' +
                    '<h1>Access Restricted</h1>' +
                    '<p>You must be at least 18 years old to enter this website.</p>' +
                    '</main>';
            });
        }
    }

    const search = document.getElementById("quiz-search");

    if (search) {
        const cards = Array.from(document.querySelectorAll("[data-search]"));
        const empty = document.getElementById("search-empty");

        search.addEventListener("input", function() {
            const term = search.value.toLowerCase().trim();
            let visible = 0;

            cards.forEach(function(card) {
                const match = (card.dataset.search || "").toLowerCase().includes(term);
                card.classList.toggle("hidden", !match);

                if (match) visible++;
            });

            if (empty) {
                empty.classList.toggle("hidden", visible !== 0);
            }
        });
    }
})();
</script>
"""

# ============================================================
# AGE VERIFICATION
# ============================================================

AGE_MODAL = """
<div class="age-overlay" id="age-overlay" role="dialog"
     aria-modal="true" aria-labelledby="age-title">
    <div class="age-modal">
        <div class="eyebrow">18+ Adult Audience</div>
        <h2 id="age-title">Welcome to Intimacy Quiz Hub</h2>
        <p>
            This website contains adult-oriented relationship and romantic
            entertainment content. Please confirm that you are at least
            18 years old before continuing.
        </p>
        <div class="age-actions">
            <button class="btn btn-green" id="age-yes">
                Yes, I am 18+
            </button>
            <button class="btn btn-outline" id="age-no">
                No, exit
            </button>
        </div>
    </div>
</div>
"""


# ============================================================
# SHARED HTML LAYOUT
# ============================================================

def header():
    return """
    <header class="site-header">
        <div class="container nav">
            <a class="brand" href="/">INTIMACY<span>QUIZ</span></a>
            <nav class="nav-links" aria-label="Main navigation">
                <a href="/">Home</a>
                <a href="/#categories">Categories</a>
                <a href="/#latest">Latest Quizzes</a>
            </nav>
        </div>
    </header>
    """


def footer():
    return f"""
    <footer class="site-footer">
        <div class="container">
            <div class="footer-grid">
                <div>
                    <h3>{esc(SITE_NAME)}</h3>
                    <p class="meta">{esc(NICHE_TOPIC)}</p>
                </div>
                <div>
                    <h3>Explore</h3>
                    <a href="/">All Quizzes</a>
                    <a href="/#categories">Quiz Categories</a>
                    <a href="/#latest">Latest Quizzes</a>
                </div>
                <div>
                    <h3>Information</h3>
                    <a href="/dmca.html">DMCA Policy</a>
                    <a href="/2257.html">18 U.S.C. 2257 Statement</a>
                    <a href="mailto:{esc(CONTACT_EMAIL)}">Contact</a>
                </div>
            </div>
            <p class="meta" style="margin-top:35px">
                © <span class="live-year">{CURRENT_YEAR}</span>
                {esc(SITE_NAME)}. All rights reserved.
                For adults aged 18 and over.
            </p>
        </div>
        <div style="background:#0d1018;border-top:1px solid #1f2433;padding:24px 16px;margin-top:40px;font-family:system-ui,-apple-system,sans-serif;text-align:center;">
            <p style="color:#9ca3af;font-size:12px;letter-spacing:1px;text-transform:uppercase;margin:0 0 12px 0;">Explore Our Interactive Network</p>
            <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px;max-width:960px;margin:0 auto;">
                <a href="https://ai-girlfriend-prompts.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">AI Girlfriend Prompts</a>
                <a href="https://couples-intimacy-games.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Couples Intimacy Games</a>
                <a href="https://fantasy-roleplay-hub.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Fantasy Roleplay Hub</a>
                <a href="https://character-persona-hub.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Character Persona Hub</a>
                <a href="https://flirty-chat-openers.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Flirty Chat Openers</a>
                <a href="https://midnight-audio-stories.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Midnight Audio Stories</a>
                <a href="https://spicy-party-games.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Spicy Party Games</a>
                <a href="https://intimacy-quiz-hub.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Intimacy Quiz Hub</a>
                <a href="https://couples-bucket-list.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Couples Bucket List</a>
                <a href="https://adult-ai-art-prompts.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Adult AI Art Prompts</a>
            </div>
        </div>
    </footer>
    """


def page_template(
    title,
    description,
    path,
    content,
    schema=None,
    extra_head="",
    include_age=True
):
    schema_html = ""

    if schema:
        schema_html = (
            '<script type="application/ld+json">'
            + safe_json(schema)
            + '</script>'
        )

    age = AGE_MODAL if include_age else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#080b0f">
<meta name="rating" content="RTA-5042-1996-1400-1577-RTA">
<meta name="description" content="{esc(truncate(description, 300))}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="google-site-verification" content="Ee2L9A2G2nVVNtBt7HiplcBJf1nSen-Rcz4sNqLuAdc" />
<meta name="msvalidate.01" content="4573069C62AEC27DA4F08DC57760BAD4" />
<title>{esc(title)}</title>
<link rel="canonical" href="{esc(canonical(path))}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(truncate(description, 200))}">
<meta property="og:url" content="{esc(canonical(path))}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(truncate(description, 200))}">
<style>{CSS}</style>
{extra_head}
{schema_html}
</head>
<body>
{header()}
<main>
{content}
</main>
{footer()}
{age}
{GLOBAL_JS}
</body>
</html>
"""


# ============================================================
# QUIZ CARD COMPONENT
# ============================================================

def quiz_card(record):
    search_content = " ".join([
        record["title"],
        record["target_keyword"],
        record["category"],
        record["subcategory"],
        " ".join(record["tags"]),
    ])

    return f"""
    <article class="card" data-search="{esc(search_content)}">
        <div class="meta">
            {esc(record["category"])} · {esc(record["subcategory"])}
        </div>
        <h3>
            <a href="/quiz/{esc(record["slug"])}.html">
                {esc(record["title"])}
            </a>
        </h3>
        <p>{esc(truncate(record["description"], 125))}</p>
        <div class="meta">
            {len(record["quiz_questions"])} questions · 3 possible answers
        </div>
        <p>
            <a class="btn" href="/quiz/{esc(record["slug"])}.html">
                Take Quiz →
            </a>
        </p>
    </article>
    """


# ============================================================
# HOMEPAGE
# ============================================================

def build_homepage(records):
    categories = defaultdict(list)
    subcategories = defaultdict(list)
    tags = defaultdict(list)

    for record in records:
        categories[record["category"]].append(record)
        subcategories[record["subcategory"]].append(record)

        for tag in record["tags"]:
            tags[tag].append(record)

    category_cards = []

    for category in sorted(categories, key=str.lower):
        items = categories[category]

        category_cards.append(f"""
        <article class="card">
            <h3>
                <a href="/category/{slugify(category)}/page-1.html">
                    {esc(category)}
                </a>
            </h3>
            <p>{len(items)} quizzes available</p>
            <a href="/category/{slugify(category)}/page-1.html">
                Explore category →
            </a>
        </article>
        """)

    subcategory_html = []

    for subcategory, items in sorted(
        subcategories.items(),
        key=lambda x: x[0].lower()
    ):
        subcategory_html.append(
            f'<a class="pill" href="/topic/{slugify(subcategory)}.html">'
            f'{esc(subcategory)} ({len(items)})</a>'
        )

    tag_html = []

    for tag, items in sorted(
        tags.items(),
        key=lambda x: (-len(x[1]), x[0].lower())
    ):
        tag_html.append(
            f'<a class="pill" href="/tag/{slugify(tag)}.html">'
            f'{esc(tag)} ({len(items)})</a>'
        )

    newest = sorted(
        records,
        key=lambda r: (r["date_object"], r["title"].lower()),
        reverse=True
    )[:NEWEST_LIMIT]

    newest_cards = "".join(quiz_card(r) for r in newest)

    content = f"""
    <section class="hero">
        <div class="container">
            <span class="eyebrow">Discover Your Relationship Style</span>
            <h1>
                Explore Your <span class="gradient">Romantic Connection</span>
            </h1>
            <p>
                Take engaging compatibility quizzes, explore romantic
                archetypes and discover new ways to connect through
                interactive relationship experiences.
            </p>
            <p style="margin-top:20px">
                <span class="updated-badge">
                    <span class="live-year">{CURRENT_YEAR}</span>
                    Evergreen Quiz Collection
                </span>
            </p>
        </div>
    </section>

    <section class="section">
        <div class="container">
            <div class="section-heading">
                <h2>Find Your Perfect Quiz</h2>
                <span class="meta">{len(records)} interactive quizzes</span>
            </div>

            <input
                id="quiz-search"
                class="search-box"
                type="search"
                placeholder="Search compatibility quizzes, keywords and tags..."
                aria-label="Search quizzes"
            >

            <div class="grid" id="quiz-results">
                {''.join(quiz_card(r) for r in records)}
            </div>

            <div id="search-empty" class="empty-state hidden">
                No matching quizzes found. Try another search.
            </div>
        </div>
    </section>

    <section class="section" id="categories">
        <div class="container">
            <div class="section-heading">
                <h2>Browse Quiz Categories</h2>
                <span class="meta">{len(categories)} unique categories</span>
            </div>
            <div class="grid">
                {''.join(category_cards)}
            </div>
        </div>
    </section>

    <section class="section">
        <div class="container">
            <h2>Explore Quiz Topics</h2>
            <p class="meta">Browse quizzes by specific subcategory.</p>
            <div>{''.join(subcategory_html)}</div>
        </div>
    </section>

    <section class="section">
        <div class="container">
            <h2>Popular Quiz Tags</h2>
            <p class="meta">Discover quizzes through related topics.</p>
            <div>{''.join(tag_html)}</div>
        </div>
    </section>

    <section class="section" id="latest">
        <div class="container">
            <div class="section-heading">
                <h2>Latest Compatibility Quizzes</h2>
                <span class="meta">30 newest available entries</span>
            </div>
            <div class="grid">
                {newest_cards}
            </div>
        </div>
    </section>

    <section class="section">
        <div class="container content">
            <h2>Discover More About Your Relationship</h2>
            <p>
                Intimacy Quiz Hub brings together interactive couples
                compatibility quizzes, romantic personality tests,
                relationship archetypes and date-night experiences.
                Explore different perspectives, start conversations
                and enjoy meaningful entertainment together.
            </p>
            <p>
                Our quizzes are designed for entertainment and
                self-reflection. They are not clinical relationship
                assessments or professional psychological evaluations.
            </p>
        </div>
    </section>
    """

    write_file(
        os.path.join(OUTPUT_DIR, "index.html"),
        page_template(
            f"{SITE_NAME} | Couples Compatibility Quizzes",
            SITE_DESCRIPTION,
            "",
            content
        )
    )


# ============================================================
# QUIZ JAVASCRIPT ENGINE
# ============================================================

def quiz_engine_js(record):
    questions = record["quiz_questions"]

    results = record["result_profiles"]

    while len(results) < 3:
        results.append(
            "Your result represents a unique relationship perspective. "
            "Use it as a conversation starter with your partner."
        )

    configuration = {
        "questions": questions,
        "results": results[:3],
        "title": record["title"],
    }

    return f"""
<script>
(function() {{
    "use strict";

    const CONFIG = {safe_json(configuration)};

    const player = document.getElementById("quiz-player");
    const resultBox = document.getElementById("quiz-result");
    const questionTitle = document.getElementById("question-title");
    const optionsContainer = document.getElementById("answer-options");
    const progress = document.getElementById("progress-fill");
    const progressLabel = document.getElementById("progress-label");
    const startButton = document.getElementById("start-quiz");
    const restartButton = document.getElementById("retake-quiz");
    const copyButton = document.getElementById("copy-result");

    let currentQuestion = 0;
    let scores = [0, 0, 0];
    let answers = [];
    let finished = false;

    function resetQuiz() {{
        currentQuestion = 0;
        scores = [0, 0, 0];
        answers = [];
        finished = false;

        resultBox.classList.add("hidden");
        player.classList.remove("hidden");

        renderQuestion();
    }}

    function renderQuestion() {{
        if (!CONFIG.questions.length) {{
            questionTitle.textContent = "No quiz questions available.";
            optionsContainer.innerHTML = "";
            return;
        }}

        const question = CONFIG.questions[currentQuestion];

        progressLabel.textContent =
            "Question " + (currentQuestion + 1) +
            " of " + CONFIG.questions.length;

        progress.style.width =
            ((currentQuestion / CONFIG.questions.length) * 100) + "%";

        questionTitle.textContent = question.question;
        optionsContainer.innerHTML = "";

        question.options.forEach(function(option, index) {{
            const button = document.createElement("button");

            button.type = "button";
            button.className = "option";
            button.textContent =
                String.fromCharCode(65 + index) + ". " + option;

            button.addEventListener("click", function() {{
                selectAnswer(index);
            }});

            optionsContainer.appendChild(button);
        }});
    }}

    function selectAnswer(index) {{
        if (finished) return;

        scores[index]++;
        answers.push(index);
        currentQuestion++;

        if (currentQuestion >= CONFIG.questions.length) {{
            showResult();
        }} else {{
            renderQuestion();
        }}
    }}

    function showResult() {{
        finished = true;

        player.classList.add("hidden");
        resultBox.classList.remove("hidden");

        const maxScore = Math.max.apply(null, scores);
        const winner = scores.indexOf(maxScore);

        const resultText = CONFIG.results[winner];

        const resultTitle = document.getElementById("result-title");
        const resultDescription = document.getElementById("result-description");

        resultTitle.textContent = [
            "Your Relationship Style",
            "Your Connection Archetype",
            "Your Compatibility Perspective"
        ][winner];

        resultDescription.textContent = resultText;

        progress.style.width = "100%";

        progressLabel.textContent = "Quiz completed";

        const shareText =
            CONFIG.title + "\\n\\n" +
            resultTitle.textContent + "\\n" +
            resultText + "\\n\\n" +
            "Discover your result at " + window.location.href;

        copyButton.onclick = async function() {{
            try {{
                if (navigator.clipboard && window.isSecureContext) {{
                    await navigator.clipboard.writeText(shareText);
                }} else {{
                    const textarea = document.createElement("textarea");
                    textarea.value = shareText;
                    textarea.style.position = "fixed";
                    textarea.style.opacity = "0";
                    document.body.appendChild(textarea);
                    textarea.select();

                    const copied = document.execCommand("copy");
                    textarea.remove();

                    if (!copied) throw new Error("Copy unavailable");
                }}

                copyButton.textContent = "Copied Successfully!";
            }} catch(error) {{
                copyButton.textContent = "Copy unavailable - select result text";
            }}
        }};
    }}

    startButton.addEventListener("click", function() {{
        resetQuiz();
    }});

    restartButton.addEventListener("click", function() {{
        resetQuiz();
    }});

    if (CONFIG.questions.length) {{
        startButton.disabled = false;
    }} else {{
        startButton.disabled = true;
        startButton.textContent = "Quiz unavailable";
    }}

}})();
</script>
"""


# ============================================================
# DETAIL PAGE SCHEMAS
# ============================================================

def quiz_schema(record):
    path = f'quiz/{record["slug"]}.html'

    faq_entities = []

    for question, answer in [
        (record["faq_q1"], record["faq_a1"]),
        (record["faq_q2"], record["faq_a2"]),
    ]:
        if question and answer:
            faq_entities.append({
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": answer
                }
            })

    return [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": record["title"],
            "description": record["description"],
            "datePublished": (
                record["date_object"].strftime("%Y-%m-%d")
                if record["date_object"] != datetime.min
                else datetime.utcnow().strftime("%Y-%m-%d")
            ),
            "dateModified": datetime.utcnow().strftime("%Y-%m-%d"),
            "author": {
                "@type": "Organization",
                "name": SITE_NAME
            },
            "publisher": {
                "@type": "Organization",
                "name": SITE_NAME
            },
            "mainEntityOfPage": canonical(path),
            "inLanguage": "en"
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Home",
                    "item": canonical()
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": record["category"],
                    "item": canonical(
                        f'category/{record["category_slug"]}/page-1.html'
                    )
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "name": record["title"],
                    "item": canonical(path)
                }
            ]
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_entities
        }
    ]


# ============================================================
# RELATED QUIZZES
# ============================================================

def find_related(record, records):
    candidates = []

    for other in records:
        if other["slug"] == record["slug"]:
            continue

        score = 0

        if other["subcategory_slug"] == record["subcategory_slug"]:
            score += 10

        if other["category_slug"] == record["category_slug"]:
            score += 3

        shared_tags = set(record["tags"]) & set(other["tags"])
        score += len(shared_tags) * 4

        if score > 0:
            candidates.append((score, other))

    candidates.sort(
        key=lambda x: (
            -x[0],
            x[1]["title"].lower()
        )
    )

    selected = [item for score, item in candidates[:RELATED_LIMIT]]

    if len(selected) < RELATED_LIMIT:
        already = {record["slug"]} | {
            item["slug"] for item in selected
        }

        for other in records:
            if other["slug"] not in already:
                selected.append(other)
                already.add(other["slug"])

            if len(selected) >= RELATED_LIMIT:
                break

    return selected[:RELATED_LIMIT]


# ============================================================
# QUIZ DETAIL PAGES
# ============================================================

def build_detail_pages(records):
    os.makedirs(os.path.join(OUTPUT_DIR, "quiz"), exist_ok=True)

    for record in records:
        slug = record["slug"]

        questions_preview = f"""
        <div class="meta">
            {len(record["quiz_questions"])} questions · 3 options each
        </div>
        """

        faq_html = ""

        for question, answer in [
            (record["faq_q1"], record["faq_a1"]),
            (record["faq_q2"], record["faq_a2"]),
        ]:
            if question and answer:
                faq_html += f"""
                <div class="faq-item">
                    <h3>{esc(question)}</h3>
                    <p>{esc(answer)}</p>
                </div>
                """

        tags_html = "".join(
            f'<a class="pill" href="/tag/{slugify(tag)}.html">'
            f'{esc(tag)}</a>'
            for tag in record["tags"]
        )

        related = find_related(record, records)

        related_html = "".join(
            quiz_card(r) for r in related
        )

        category_path = (
            f'/category/{record["category_slug"]}/page-1.html'
        )

        topic_path = (
            f'/topic/{record["subcategory_slug"]}.html'
        )

        content = f"""
        <div class="container">
            <div class="breadcrumb">
                <a href="/">Home</a> /
                <a href="{category_path}">{esc(record["category"])}</a> /
                {esc(record["title"])}
            </div>

            <article class="content">
                <span class="eyebrow">
                    Interactive Compatibility Quiz
                </span>

                <h1>{esc(record["title"])}</h1>

                <p>{esc(record["description"])}</p>

                <div class="meta">
                    Category:
                    <a href="{category_path}">
                        {esc(record["category"])}
                    </a>
                    ·
                    <a href="{topic_path}">
                        {esc(record["subcategory"])}
                    </a>
                </div>

                <p style="margin-top:20px">
                    <span class="updated-badge updated-quiz-edition">
                        Updated Quiz Edition • {datetime.utcnow().strftime("%B %Y")}
                    </span>
                </p>

                {questions_preview}

                <!-- AD_SLOT_TOP_BANNER -->

                <section class="quiz-shell" id="quiz-section">
                    <div class="quiz-status">
                        <span id="progress-label">Ready to begin</span>
                        <span>Interactive Quiz</span>
                    </div>

                    <div class="progress-track">
                        <div class="progress-fill" id="progress-fill"></div>
                    </div>

                    <div id="quiz-player">
                        <h2>Discover Your Relationship Perspective</h2>
                        <p>
                            Answer each question honestly.
                            Your answers will reveal one of three
                            possible result profiles.
                        </p>

                        <button class="btn btn-green" id="start-quiz">
                            Start Your Quiz →
                        </button>

                        <div id="question-container">
                            <h2 class="question-title" id="question-title"></h2>
                            <div id="answer-options"></div>
                        </div>
                    </div>

                    <div id="quiz-result" class="hidden">
                        <div class="result-box">
                            <span class="eyebrow">Your Quiz Result</span>

                            <h2 id="result-title">
                                Your Relationship Style
                            </h2>

                            <p id="result-description"></p>

                            <button class="btn btn-green" id="copy-result">
                                Copy Result to Share with Partner
                            </button>

                            <button class="btn btn-outline"
                                    id="retake-quiz">
                                Retake Quiz
                            </button>

                            <div class="affiliate">
                                <div class="eyebrow">Discover Your Next Match</div>
                                <h3>Take Your Connection Further</h3>
                                <p>
                                    Explore another personalized experience
                                    inspired by your quiz result.
                                </p>
                                <a class="btn" href="{esc(AFFILIATE_URL)}"
                                   rel="nofollow sponsored">
                                    {esc(AFFILIATE_CTA_TEXT)} →
                                </a>
                            </div>
                        </div>
                    </div>
                </section>

                <!-- AD_SLOT_MID_CONTENT -->

                <h2>About This Compatibility Quiz</h2>

                <p>
                    This interactive quiz explores different relationship
                    perspectives through a sequence of multiple-choice
                    questions. It is designed to encourage conversation,
                    self-reflection and enjoyable shared experiences.
                </p>

                <h2>Explore Related Topics</h2>
                <p>{tags_html}</p>

                <h2>Frequently Asked Questions</h2>
                {faq_html if faq_html else
                '<p>Explore the quiz to discover more about your results.</p>'}

                <p class="meta">
                    Last generated:
                    <span class="live-year">{CURRENT_YEAR}</span>
                </p>
            </article>
        </div>

        <section class="section">
            <div class="container">
                <div class="section-heading">
                    <h2>Related Compatibility Quizzes</h2>
                    <span class="meta">Discover more experiences</span>
                </div>
                <div class="grid">
                    {related_html}
                </div>
            </div>
        </section>
        """

        full_html = page_template(
            f'{record["title"]} | {SITE_NAME}',
            record["description"],
            f"quiz/{slug}.html",
            content,
            schema=quiz_schema(record),
            extra_head=(
                f'<meta property="og:type" content="article">'
            )
        )

        full_html = full_html.replace(
            "</body>",
            quiz_engine_js(record) + "\n</body>"
        )

        full_html = full_html.replace(
            '<footer class="site-footer">',
            '<!-- AD_SLOT_STICKY_FOOTER -->\n'
            '<footer class="site-footer">'
        )

        full_html = full_html.replace(
            "<body>",
            "<body>\n<!-- AD_SLOT_POPUNDER -->"
        )

        write_file(
            os.path.join(OUTPUT_DIR, "quiz", slug + ".html"),
            full_html
        )


# ============================================================
# CATEGORY HUBS WITH PAGINATION
# ============================================================

def build_category_hubs(records):
    grouped = defaultdict(list)

    for record in records:
        grouped[record["category_slug"]].append(record)

    for category_slug, items in grouped.items():

        items.sort(
            key=lambda r: (
                r["date_object"],
                r["title"].lower()
            ),
            reverse=True
        )

        category_name = items[0]["category"]

        total_pages = max(
            1,
            (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        )

        for page_number in range(1, total_pages + 1):

            start = (page_number - 1) * ITEMS_PER_PAGE
            end = start + ITEMS_PER_PAGE

            page_items = items[start:end]

            current_path = (
                f"category/{category_slug}/page-{page_number}.html"
            )

            extra_head = ""

            if page_number > 1:
                extra_head += (
                    f'<link rel="prev" href="{esc(canonical(
                        f"category/{category_slug}/page-{page_number - 1}.html"
                    ))}">'
                )

            if page_number < total_pages:
                extra_head += (
                    f'<link rel="next" href="{esc(canonical(
                        f"category/{category_slug}/page-{page_number + 1}.html"
                    ))}">'
                )

            pagination = []

            if page_number > 1:
                pagination.append(
                    f'<a class="btn btn-outline" href="page-{page_number - 1}.html">← Previous</a>'
                )

            for p in range(1, total_pages + 1):
                if p == page_number:
                    pagination.append(
                        f'<span class="pill">{p}</span>'
                    )
                else:
                    pagination.append(
                        f'<a class="pill" href="page-{p}.html">{p}</a>'
                    )

            if page_number < total_pages:
                pagination.append(
                    f'<a class="btn" href="page-{page_number + 1}.html">Next →</a>'
                )

            content = f"""
            <section class="hero">
                <div class="container">
                    <span class="eyebrow">Quiz Category</span>
                    <h1>{esc(category_name)}</h1>
                    <p>
                        Explore {len(items)} interactive quizzes
                        in this category.
                    </p>
                    <p class="meta">
                        Page {page_number} of {total_pages}
                    </p>
                </div>
            </section>

            <section class="section">
                <div class="container">
                    <div class="grid">
                        {''.join(quiz_card(r) for r in page_items)}
                    </div>

                    <div class="pagination">
                        {''.join(pagination)}
                    </div>
                </div>
            </section>
            """

            directory = os.path.join(
                OUTPUT_DIR,
                "category",
                category_slug
            )

            write_file(
                os.path.join(
                    directory,
                    f"page-{page_number}.html"
                ),
                page_template(
                    f"{category_name} Quizzes | Page {page_number} | {SITE_NAME}",
                    f"Explore {len(items)} {category_name.lower()} quizzes and interactive relationship experiences.",
                    current_path,
                    content,
                    extra_head=extra_head
                )
            )


# ============================================================
# SUBCATEGORY HUBS
# ============================================================

def build_topic_hubs(records):
    grouped = defaultdict(list)

    for record in records:
        grouped[record["subcategory_slug"]].append(record)

    for topic_slug, items in grouped.items():

        topic_name = items[0]["subcategory"]

        items.sort(
            key=lambda r: r["title"].lower()
        )

        content = f"""
        <section class="hero">
            <div class="container">
                <span class="eyebrow">Explore Quiz Topics</span>
                <h1>{esc(topic_name)}</h1>
                <p>
                    Discover {len(items)} quizzes related to
                    {esc(topic_name.lower())}.
                </p>
            </div>
        </section>

        <section class="section">
            <div class="container">
                <div class="grid">
                    {''.join(quiz_card(r) for r in items)}
                </div>
            </div>
        </section>
        """

        write_file(
            os.path.join(
                OUTPUT_DIR,
                "topic",
                topic_slug + ".html"
            ),
            page_template(
                f"{topic_name} Quizzes | {SITE_NAME}",
                f"Explore {len(items)} interactive quizzes about {topic_name}.",
                f"topic/{topic_slug}.html",
                content
            )
        )


# ============================================================
# TAG HUBS
# ============================================================

def build_tag_hubs(records):
    grouped = defaultdict(list)

    for record in records:
        for tag in record["tags"]:
            grouped[slugify(tag)].append(record)

    for tag_slug, items in grouped.items():

        tag_name = next(
            (
                tag
                for record in items
                for tag in record["tags"]
                if slugify(tag) == tag_slug
            ),
            tag_slug.replace("-", " ").title()
        )

        items.sort(
            key=lambda r: r["title"].lower()
        )

        content = f"""
        <section class="hero">
            <div class="container">
                <span class="eyebrow">Quiz Tag</span>
                <h1>{esc(tag_name)}</h1>
                <p>
                    Browse {len(items)} interactive quizzes
                    related to {esc(tag_name.lower())}.
                </p>
            </div>
        </section>

        <section class="section">
            <div class="container">
                <div class="grid">
                    {''.join(quiz_card(r) for r in items)}
                </div>
            </div>
        </section>
        """

        write_file(
            os.path.join(
                OUTPUT_DIR,
                "tag",
                tag_slug + ".html"
            ),
            page_template(
                f"{tag_name} Quizzes | {SITE_NAME}",
                f"Discover {len(items)} relationship quizzes about {tag_name}.",
                f"tag/{tag_slug}.html",
                content
            )
        )


# ============================================================
# LEGAL AND INFORMATION PAGES
# ============================================================

def build_legal_pages():
    dmca_content = f"""
    <section class="section">
        <div class="container content">
            <span class="eyebrow">Website Information</span>
            <h1>DMCA Copyright Policy</h1>

            <p>
                {esc(SITE_NAME)} respects intellectual property rights
                and expects contributors and visitors to do the same.
            </p>

            <h2>Copyright Complaints</h2>

            <p>
                If you believe material published on this website infringes
                your copyright, you may submit a written notice to:
            </p>

            <p><strong>Email:</strong>
                <a href="mailto:{esc(CONTACT_EMAIL)}">
                    {esc(CONTACT_EMAIL)}
                </a>
            </p>

            <h2>Information to Include</h2>

            <ul>
                <li>Identification of the copyrighted work.</li>
                <li>The URL of the allegedly infringing material.</li>
                <li>Your contact information.</li>
                <li>A statement of good-faith belief.</li>
                <li>A statement that your notice is accurate and authorized.</li>
                <li>Your physical or electronic signature.</li>
            </ul>

            <h2>Review Process</h2>

            <p>
                Notices will be reviewed and appropriate action may be
                taken where legally required. Incomplete or misleading
                notices may require additional information.
            </p>

            <h2>Contact</h2>
            <p>
                Copyright inquiries:
                <a href="mailto:{esc(CONTACT_EMAIL)}">
                    {esc(CONTACT_EMAIL)}
                </a>
            </p>
        </div>
    </section>
    """

    write_file(
        os.path.join(OUTPUT_DIR, "dmca.html"),
        page_template(
            f"DMCA Copyright Policy | {SITE_NAME}",
            "Copyright policy and procedure for submitting copyright complaints.",
            "dmca.html",
            dmca_content
        )
    )

    compliance_content = f"""
    <section class="section">
        <div class="container content">
            <span class="eyebrow">Compliance Information</span>
            <h1>18 U.S.C. § 2257 Statement</h1>

            <h2>Nature of Website Content</h2>

            <p>
                {esc(SITE_NAME)} primarily publishes original
                text-based relationship quizzes, interactive
                questionnaires, personality-style content and
                informational material.
            </p>

            <p>
                The website does not intentionally publish sexually
                explicit visual depictions of actual human beings.
                Its interactive experiences are intended for an
                adult audience aged 18 and over.
            </p>

            <h2>Applicability</h2>

            <p>
                The applicability of 18 U.S.C. § 2257 and related
                regulations depends on the nature of the material
                and the role of the relevant entity. This statement
                is informational and is not a representation that
                every possible statutory exemption applies.
            </p>

            <h2>Contact</h2>

            <p>
                For compliance inquiries, contact:
                <a href="mailto:{esc(CONTACT_EMAIL)}">
                    {esc(CONTACT_EMAIL)}
                </a>
            </p>

            <p class="meta">
                This page is not legal advice.
                Obtain qualified legal advice where necessary.
            </p>
        </div>
    </section>
    """

    write_file(
        os.path.join(OUTPUT_DIR, "2257.html"),
        page_template(
            f"18 U.S.C. 2257 Statement | {SITE_NAME}",
            "Information about the nature of this website's text-based content and applicable compliance disclosures.",
            "2257.html",
            compliance_content
        )
    )


# ============================================================
# XML SITEMAP XSL
# ============================================================

def build_sitemap_xsl():
    xsl = r"""<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
xmlns:s="http://www.sitemaps.org/schemas/sitemap/0.9">
<xsl:output method="html" encoding="UTF-8" indent="yes"/>
<xsl:template match="/">
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>XML Sitemap - Intimacy Quiz Hub</title>
<style>
body{background:#080b0f;color:#f3f4f6;font-family:system-ui;padding:30px}
main{max-width:1000px;margin:auto}
h1{color:#10b981}
p{color:#9ca3af}
table{width:100%;border-collapse:collapse;background:#111722}
th,td{padding:13px;border:1px solid #263244;text-align:left}
th{color:#ec4899}
a{color:#10b981;word-break:break-all}
tr:hover{background:#18212d}
</style>
</head>
<body>
<main>
<h1>Intimacy Quiz Hub Sitemap</h1>
<p>Automatically generated website URLs.</p>
<table>
<tr><th>URL</th><th>Last Modified</th><th>Priority</th></tr>
<xsl:for-each select="s:urlset/s:url">
<tr>
<td><a href="{s:loc}"><xsl:value-of select="s:loc"/></a></td>
<td><xsl:value-of select="s:lastmod"/></td>
<td><xsl:value-of select="s:priority"/></td>
</tr>
</xsl:for-each>
</table>
</main>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
"""

    write_file(
        os.path.join(OUTPUT_DIR, "sitemap.xsl"),
        xsl
    )


# ============================================================
# XML SITEMAPS
# ============================================================

def build_sitemaps(records):
    urls = {}

    def add_url(path, priority="0.7", frequency="monthly"):
        full_url = canonical(path)

        urls[full_url] = {
            "loc": full_url,
            "lastmod": datetime.utcnow().strftime("%Y-%m-%d"),
            "changefreq": frequency,
            "priority": priority,
        }

    add_url("", "1.0", "weekly")
    add_url("dmca.html", "0.2", "yearly")
    add_url("2257.html", "0.2", "yearly")

    for record in records:
        add_url(f'quiz/{record["slug"]}.html', "0.9", "monthly")

    categories = defaultdict(list)
    topics = set()
    tags = set()

    for record in records:
        categories[record["category_slug"]].append(record)
        topics.add(record["subcategory_slug"])

        for tag in record["tags"]:
            tags.add(slugify(tag))

    for category_slug, items in categories.items():
        pages = max(
            1,
            (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        )

        for page in range(1, pages + 1):
            add_url(
                f"category/{category_slug}/page-{page}.html",
                "0.8",
                "weekly"
            )

    for topic in topics:
        add_url(f"topic/{topic}.html", "0.7", "monthly")

    for tag in tags:
        add_url(f"tag/{tag}.html", "0.6", "monthly")

    all_urls = list(urls.values())

    chunks = [
        all_urls[i:i + SITEMAP_LIMIT]
        for i in range(0, len(all_urls), SITEMAP_LIMIT)
    ]

    if not chunks:
        chunks = [[]]

    def build_urlset(chunk):
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<?xml-stylesheet type="text/xsl" href="/sitemap.xsl"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        ]

        for item in chunk:
            lines.append("<url>")
            lines.append(f'<loc>{html.escape(item["loc"])}</loc>')
            lines.append(f'<lastmod>{item["lastmod"]}</lastmod>')
            lines.append(
                f'<changefreq>{item["changefreq"]}</changefreq>'
            )
            lines.append(
                f'<priority>{item["priority"]}</priority>'
            )
            lines.append("</url>")

        lines.append("</urlset>")

        return "\n".join(lines)

    if len(chunks) == 1:
        write_file(
            os.path.join(OUTPUT_DIR, "sitemap-1.xml"),
            build_urlset(chunks[0])
        )

        # Sitemap index remains the public sitemap entry point.
        index = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap>
<loc>{esc(canonical("sitemap-1.xml"))}</loc>
<lastmod>{datetime.utcnow().strftime("%Y-%m-%d")}</lastmod>
</sitemap>
</sitemapindex>"""

    else:
        sitemap_entries = []

        for index_number, chunk in enumerate(chunks, start=1):
            filename = f"sitemap-{index_number}.xml"

            write_file(
                os.path.join(OUTPUT_DIR, filename),
                build_urlset(chunk)
            )

            sitemap_entries.append(
                f"""
                <sitemap>
                    <loc>{esc(canonical(filename))}</loc>
                    <lastmod>{datetime.utcnow().strftime("%Y-%m-%d")}</lastmod>
                </sitemap>
                """
            )

        index = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(sitemap_entries)
            + "</sitemapindex>"
        )

    write_file(
        os.path.join(OUTPUT_DIR, "sitemap.xml"),
        index
    )

    build_sitemap_xsl()

    robots = f"""User-agent: *
Allow: /

Sitemap: {canonical("sitemap.xml")}
"""

    write_file(
        os.path.join(OUTPUT_DIR, "robots.txt"),
        robots
    )


# ============================================================
# ADDITIONAL STATIC SEO FILES
# ============================================================

def build_web_manifest():
    manifest = {
        "name": SITE_NAME,
        "short_name": "Intimacy Quiz",
        "description": SITE_DESCRIPTION,
        "start_url": "/",
        "display": "standalone",
        "background_color": "#080b0f",
        "theme_color": "#080b0f",
        "orientation": "portrait"
    }

    write_file(
        os.path.join(OUTPUT_DIR, "site.webmanifest"),
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )


def build_404():
    content = """
    <section class="hero">
        <div class="container">
            <span class="eyebrow">404 Error</span>
            <h1>Page Not Found</h1>
            <p>
                The page you are looking for may have moved
                or no longer exists.
            </p>
            <p style="margin-top:25px">
                <a href="/" class="btn">Return Home</a>
            </p>
        </div>
    </section>
    """

    write_file(
        os.path.join(OUTPUT_DIR, "404.html"),
        page_template(
            f"Page Not Found | {SITE_NAME}",
            "The requested page could not be found.",
            "404.html",
            content
        )
    )


# ============================================================
# VALIDATION AND BUILD REPORT
# ============================================================

def validate_output(records):
    errors = []

    for record in records:
        path = os.path.join(
            OUTPUT_DIR,
            "quiz",
            record["slug"] + ".html"
        )

        if not os.path.exists(path):
            errors.append(f"Missing detail page: {path}")
            continue

        with open(path, "r", encoding="utf-8") as file:
            content = file.read()

        required = [
            'name="description"',
            'rel="canonical"',
            'name="rating"',
            'application/ld+json',
            'id="quiz-player"',
            'id="quiz-result"',
            'id="copy-result"',
            'id="retake-quiz"',
            "AD_SLOT_TOP_BANNER",
            "AD_SLOT_MID_CONTENT",
            "AD_SLOT_POPUNDER",
            "AD_SLOT_STICKY_FOOTER",
        ]

        for item in required:
            if item not in content:
                errors.append(
                    f"{record['slug']}: missing {item}"
                )

    for filename in [
        "index.html",
        "sitemap.xml",
        "sitemap-1.xml",
        "sitemap.xsl",
        "robots.txt",
        "dmca.html",
        "2257.html",
        "404.html",
    ]:
        path = os.path.join(OUTPUT_DIR, filename)

        if not os.path.exists(path):
            errors.append(f"Missing output file: {filename}")

    if errors:
        print("\nBUILD VALIDATION WARNINGS:")

        for error in errors:
            print(" -", error)

        return False

    return True


def print_report(records):
    categories = Counter(r["category"] for r in records)

    topics = Counter(r["subcategory"] for r in records)

    all_tags = Counter(
        tag
        for record in records
        for tag in record["tags"]
    )

    detail_pages = len(records)

    category_pages = sum(
        max(
            1,
            (count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        )
        for count in categories.values()
    )

    topic_pages = len(topics)
    tag_pages = len(all_tags)

    total_pages = (
        1
        + detail_pages
        + category_pages
        + topic_pages
        + tag_pages
        + 5
    )

    print("\n" + "=" * 60)
    print("       INTIMACY QUIZ HUB — BUILD COMPLETE")
    print("=" * 60)

    print(f"Website:             {BASE_URL}")
    print(f"Site name:           {SITE_NAME}")
    print(f"Current build year:  {CURRENT_YEAR}")
    print(f"Quiz records:        {len(records)}")
    print(f"Unique categories:   {len(categories)}")
    print(f"Unique subcategories:{topic_pages}")
    print(f"Unique tags:         {tag_pages}")

    print("-" * 60)

    print(f"Detail pages:        {detail_pages}")
    print(f"Category pages:      {category_pages}")
    print(f"Topic pages:         {topic_pages}")
    print(f"Tag pages:           {tag_pages}")
    print(f"Estimated HTML pages:{total_pages}")

    print("-" * 60)

    print("Generated files:")
    print("  dist/index.html")
    print("  dist/quiz/*.html")
    print("  dist/category/*/page-*.html")
    print("  dist/topic/*.html")
    print("  dist/tag/*.html")
    print("  dist/sitemap.xml")
    print("  dist/sitemap-1.xml")
    print("  dist/sitemap.xsl")
    print("  dist/robots.txt")
    print("  dist/dmca.html")
    print("  dist/2257.html")
    print("  dist/404.html")
    print("  dist/site.webmanifest")

    print("-" * 60)

    if validate_output(records):
        print("Validation:          PASSED")
    else:
        print("Validation:          COMPLETED WITH WARNINGS")

    print("=" * 60)
    print("Deployment directory: dist/")
    print("=" * 60)


# ============================================================
# MAIN BUILD PROCESS
# ============================================================

def main():
    print("\nStarting Intimacy Quiz Hub build...")
    print(f"Reading input: {INPUT_FILE}")

    records = load_data()

    print(f"Loaded {len(records)} quiz records.")

    # Start with a clean output directory.
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nGenerating homepage...")
    build_homepage(records)

    print("Generating interactive quiz detail pages...")
    build_detail_pages(records)

    print("Generating paginated category hubs...")
    build_category_hubs(records)

    print("Generating dedicated topic hubs...")
    build_topic_hubs(records)

    print("Generating dedicated tag hubs...")
    build_tag_hubs(records)

    print("Generating legal and information pages...")
    build_legal_pages()

    print("Generating sitemaps and robots.txt...")
    build_sitemaps(records)

    print("Generating web manifest and 404 page...")
    build_web_manifest()
    build_404()

    print_report(records)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBuild cancelled.")
        raise SystemExit(130)
    except Exception as error:
        print("\nBUILD FAILED:")
        print(str(error))
        raise SystemExit(1)
