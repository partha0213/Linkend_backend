import argparse
import json
import logging
import os
import pickle
import random
import re
import time
import html
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# ---------- Selenium / undetected-chromedriver ----------
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, JavascriptException, NoSuchElementException
except Exception:
    print("[FATAL] Missing selenium/undetected_chromedriver. Please: pip install undetected-chromedriver selenium")
    raise

# ---------- OpenAI (optional) ----------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# =========================
# Logging
# =========================
logging.basicConfig(
    format="[%(levelname)s] %(asctime)s %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================
# ENV & CONFIG
# =========================
load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "").strip()
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "").strip()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
try:
    TELEGRAM_CHAT_ID = int(str(os.getenv("TELEGRAM_CHAT_ID", "0")).strip())
except Exception:
    TELEGRAM_CHAT_ID = 0

HEADLESS = os.getenv("HEADLESS", "0") == "1"
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.pkl")
STATE_FILE = os.getenv("STATE_FILE", "./linkedin_seen_state.json")
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "300"))
CHECK_INTERVAL_MAX = int(os.getenv("CHECK_INTERVAL_MAX", "600"))

CHROME_BINARY_PATH = os.getenv("CHROME_BINARY_PATH", "").strip()
# New: allow using a persistent Chrome profile (most reliable login path)
CHROME_USER_DATA_DIR = os.getenv("CHROME_USER_DATA_DIR", "").strip()  # e.g., C:\Users\<you>\AppData\Local\Google\Chrome\User Data
CHROME_PROFILE_DIR   = os.getenv("CHROME_PROFILE_DIR", "Default").strip()  # e.g., "Default" or "Profile 1"

# Historical data settings
INITIAL_MONTHS_BACK = int(os.getenv("INITIAL_MONTHS_BACK", "2"))
INITIAL_SCROLL_LIMIT = int(os.getenv("INITIAL_SCROLL_LIMIT", "20"))  # More scrolling for historical data
NORMAL_SCROLL_LIMIT = int(os.getenv("NORMAL_SCROLL_LIMIT", "6"))    # Normal monitoring scrolls

# LLM Token Management
MAX_TOKENS_HISTORICAL = int(os.getenv("MAX_TOKENS_HISTORICAL", "800"))  # Lower for historical (many posts)
MAX_TOKENS_NORMAL = int(os.getenv("MAX_TOKENS_NORMAL", "1200"))        # Higher for normal monitoring
MAX_PAST_POSTS_HISTORICAL = int(os.getenv("MAX_PAST_POSTS_HISTORICAL", "3"))  # Fewer context posts for historical
MAX_PAST_POSTS_NORMAL = int(os.getenv("MAX_PAST_POSTS_NORMAL", "5"))          # More context for normal

PROFILES_RAW = os.getenv("PROFILES", "").strip()
PROFILES: List[str] = [p.strip() for p in PROFILES_RAW.split(",") if p.strip()]
if not PROFILES:
    PROFILES = [
        "https://www.linkedin.com/in/sethu-raman-931a62211",
        "https://www.linkedin.com/in/kathiravanm232003/",
    ]

def _get_first_env(*names: str) -> str:
    for n in names:
        v = os.getenv(n, "").strip()
        if v:
            return v
    return ""

OPENAI_API_KEY = _get_first_env("OPENAI_API_KEY", "OPENAI_API_TOKEN", "OPENAI_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-3.5-turbo").strip()
client = None
if OpenAI is None:
    logger.info("OpenAI SDK not available; LLM features disabled.")
elif not OPENAI_API_KEY:
    logger.info("No OPENAI_API_KEY found; LLM features disabled.")
else:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info(f"OpenAI client initialized; model='{OPENAI_MODEL}'.")
    except Exception as e:
        logger.warning(f"OpenAI client init failed: {e}")
        client = None

# Patch: avoid WinError 6 destructor bug
try:
    uc.Chrome.__del__ = lambda self: None
except Exception:
    pass

# =========================
# Utils
# =========================
def safe_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, (list, tuple, set)):
        return ", ".join(safe_str(x) for x in v)
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)

def jitter_sleep(a: int, b: int) -> float:
    t = random.randint(a, b)
    logger.info(f"Waiting {t} seconds...")
    time.sleep(t)
    return float(t)

def safe_save_json(path: str, data: dict) -> None:
    d = os.path.dirname(path) or "."
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_load_json(path: str, default: dict) -> dict:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load JSON {path}: {e}")
        return default

# =========================
# Telegram
# =========================
def is_telegram_configured() -> bool:
    return bool(TELEGRAM_TOKEN) and TELEGRAM_CHAT_ID != 0

def send_telegram_html(text: str) -> None:
    if not text:
        return
    if not is_telegram_configured():
        logger.debug("Telegram not configured — skipping send.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    CHUNK = 3500
    parts = [text[i:i+CHUNK] for i in range(0, len(text), CHUNK)]
    for idx, p in enumerate(parts, 1):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": p,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code != 200:
                logger.warning(f"Telegram send failed (part {idx}): {r.status_code} - {r.text}")
        except Exception as e:
            logger.warning(f"Telegram send exception (part {idx}): {e}")

# =========================
# Helper: names/urls
# =========================
def extract_profile_slug(profile_url) -> str:
    if isinstance(profile_url, (list, tuple)):
        profile_url = profile_url if profile_url else ""
    profile_url = str(profile_url or "")
    u = [x for x in profile_url.rstrip("/").split("/") if x]
    if len(u) >= 2 and u[-2] in ("in", "company"):
        return u[-1]
    return u[-1] if u else profile_url

def display_name_from_url(profile_url) -> str:
    slug = extract_profile_slug(profile_url)
    name = re.sub(r"-\d+$", "", slug)
    name = name.replace("-", " ").strip()
    return name.title() if name else slug

def display_name_with_suffix(profile_url) -> str:
    name = display_name_from_url(profile_url)
    slug = extract_profile_slug(profile_url)
    m = re.search(r"-([a-z0-9]+)$", slug)
    if m:
        return f"{name} {m.group(1).upper()}"
    return name

# =========================
# Driver + waits
# =========================
def build_driver():
    chrome_options = Options()
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-features=RendererCodeIntegrity")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    # Use a real Chrome if provided (helps with stability)
    if CHROME_BINARY_PATH and os.path.exists(CHROME_BINARY_PATH):
        chrome_options.binary_location = CHROME_BINARY_PATH

    # Most reliable: reuse a real Chrome profile (already signed in)
    if CHROME_USER_DATA_DIR:
        chrome_options.add_argument(f'--user-data-dir={CHROME_USER_DATA_DIR}')
        if CHROME_PROFILE_DIR:
            chrome_options.add_argument(f'--profile-directory={CHROME_PROFILE_DIR}')

    if HEADLESS:
        chrome_options.add_argument("--headless=new")

    driver = uc.Chrome(options=chrome_options)
    driver.set_page_load_timeout(120)
    return driver

def goto(driver, url: str, wait_css_any: Optional[List[str]] = None, max_wait: int = 35, retries: int = 2):
    last_err = None
    for attempt in range(retries + 1):
        try:
            try:
                driver.get(url)
            except TimeoutException:
                pass
            WebDriverWait(driver, max_wait).until(
                lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
            )
            if wait_css_any:
                ok = False
                for sel in wait_css_any:
                    try:
                        WebDriverWait(driver, max_wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                        ok = True
                        break
                    except TimeoutException:
                        continue
                if not ok:
                    raise TimeoutException(f"None of selectors present: {wait_css_any}")
            return
        except (TimeoutException, JavascriptException) as e:
            last_err = e
            time.sleep(2 + attempt)
            continue
    raise last_err if last_err else TimeoutException("goto failed")

# =========================
# Login / cookies
# =========================
def wait_for_feed(driver, max_wait: int = 15) -> bool:
    try:
        WebDriverWait(driver, max_wait).until(lambda d: "/feed" in (d.current_url or "").lower())
        # also wait for the nav/compose to be present (signals real feed)
        WebDriverWait(driver, max_wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "header.global-nav, div.share-box-feed-entry__closed-share-box"))
        )
        return True
    except TimeoutException:
        return False

def is_checkpoint(driver) -> bool:
    cur = (driver.current_url or "").lower()
    return "/checkpoint/" in cur or "/authwall" in cur

def accept_cookie_banner_if_present(driver):
    try:
        # EU cookie banner etc.
        btns = driver.find_elements(By.XPATH, "//button//*[contains(text(),'Accept') or contains(text(),'agree')]/..")
        for b in btns:
            try:
                b.click()
                time.sleep(1)
                return
            except Exception:
                continue
    except Exception:
        pass

def save_cookies(driver, path=COOKIES_FILE):
    try:
        with open(path, "wb") as file:
            pickle.dump(driver.get_cookies(), file)
        logger.info(f"Saved cookies to {path}")
    except Exception as e:
        logger.warning(f"Failed to save cookies: {e}")

def load_cookies(driver, path=COOKIES_FILE) -> bool:
    if not os.path.exists(path):
        return False
    try:
        goto(driver, "https://www.linkedin.com", wait_css_any=["body"])
        with open(path, "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies:
                if not isinstance(cookie, dict):
                    continue
                # sanitize cookie to avoid Selenium complaints
                cookie.pop("sameSite", None)
                if "expiry" in cookie and not isinstance(cookie["expiry"], (int, float)):
                    cookie.pop("expiry", None)
                domain = cookie.get("domain")
                if domain and "linkedin" not in domain:
                    cookie["domain"] = ".linkedin.com"
                if not cookie.get("name") or cookie.get("value") is None:
                    continue
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    continue
        driver.refresh()
        time.sleep(2)
        goto(driver, "https://www.linkedin.com/feed/", wait_css_any=["body"], max_wait=40)
        if wait_for_feed(driver, 12) and not is_checkpoint(driver):
            logger.info("Session restored from cookies.")
            return True
        logger.info("Cookies present but not valid anymore.")
        return False
    except Exception as e:
        logger.warning(f"Failed to load cookies: {e}")
        return False

def login_with_credentials(driver):
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        raise ValueError("Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env for credential login.")

    logger.info("Attempting credential login...")
    goto(driver, "https://www.linkedin.com/login", wait_css_any=["#username", "#password"], max_wait=40)
    accept_cookie_banner_if_present(driver)

    email_input = driver.find_element(By.ID, "username")
    password_input = driver.find_element(By.ID, "password")

    email_input.clear(); email_input.send_keys(LINKEDIN_EMAIL)
    password_input.clear(); password_input.send_keys(LINKEDIN_PASSWORD)
    password_input.submit()

    # Wait for either feed or login error/checkpoint
    ok = wait_for_feed(driver, 20)
    if ok and not is_checkpoint(driver):
        logger.info("Credential login successful.")
        save_cookies(driver)
        return

    # If there is an error message on the login page
    try:
        err = driver.find_element(By.CSS_SELECTOR, ".alert.error, .form__decorative-error").text.strip()
        if err:
            raise RuntimeError(f"Login error: {err}")
    except NoSuchElementException:
        pass

    if is_checkpoint(driver):
        raise RuntimeError("LinkedIn requested verification (checkpoint/authwall). Complete it once in a non-headless browser with your profile dir, then re-run.")

    raise RuntimeError("Login failed: could not reach /feed.")

def ensure_logged_in(driver):
    """
    Multi-path login:
      1) If CHROME_USER_DATA_DIR has a valid LinkedIn session -> save cookies and continue.
      2) Else try COOKIES_FILE.
      3) Else credential login.
    """
    logger.info("Ensuring LinkedIn session...")
    # 1) If using a persistent Chrome profile, try feed first
    try:
        goto(driver, "https://www.linkedin.com/feed/", wait_css_any=["body"], max_wait=40)
        if wait_for_feed(driver, 10) and not is_checkpoint(driver):
            logger.info("Logged in via Chrome profile session.")
            save_cookies(driver)
            return
    except Exception:
        pass

    # 2) Try cookies
    if load_cookies(driver):
        return

    # 3) Credentials
    login_with_credentials(driver)

# =========================
# Scrapers
# =========================
def human_sleep(base: float = 3.0, var: float = 2.0):
    time.sleep(base + random.uniform(0, var))

def build_activity_urls(profile_base: str) -> Tuple[str, str, str, str]:
    base = str(profile_base).rstrip("/")
    return (
        base + "/recent-activity/all/",
        base + "/recent-activity/shares/",
        base + "/recent-activity/comments/",
        base + "/recent-activity/reactions/",
    )

def _extract_post_link(block):
    try:
        a = block.find_element(By.CSS_SELECTOR, 'a.app-aware-link[href*="/feed/update/"]')
        href = a.get_attribute("href")
        if href: return href
    except Exception: pass
    try:
        a = block.find_element(By.XPATH, ".//a[contains(@href,'/feed/update/')]")
        href = a.get_attribute("href")
        if href: return href
    except Exception: pass
    return ""

def _extract_post_author_slug(block) -> str:
    """
    Try to identify the author of the post being referenced inside a comment/like block.
    Returns a slug such as "sethu-raman-931a62211" or "company-name" if found, else empty.
    """
    # Common patterns for author anchors on activity cards
    candidates = [
        (By.CSS_SELECTOR, "a.app-aware-link[href*='/in/']"),
        (By.CSS_SELECTOR, "a.app-aware-link[href*='/company/']"),
        (By.XPATH, ".//a[contains(@href,'/in/') or contains(@href,'/company/')]")
    ]
    for by, selector in candidates:
        try:
            a = block.find_element(by, selector)
            href = a.get_attribute("href") or ""
            if "/in/" in href or "/company/" in href:
                parts = [x for x in href.rstrip("/").split("/") if x]
                if len(parts) >= 2 and parts[-2] in ("in", "company"):
                    return parts[-1]
        except Exception:
            continue
    return ""
def _extract_text_with_fallback(block) -> str:
    for by, sel in [
        (By.CSS_SELECTOR, "div.update-components-text"),
        (By.XPATH, ".//div[contains(@class,'update-components-text')]"),
        (By.XPATH, ".//span[@dir='ltr']"),
        (By.XPATH, ".//*[contains(@class,'break-words')]"),
    ]:
        try:
            el = block.find_element(by, sel)
            t = (el.text or "").strip()
            if t: return t
        except Exception: continue
    return (block.text or "").strip()

def scrape_profile_activity(driver, profile_url: str, limit: int = 6, is_historical: bool = False) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    _, posts_url, comments_url, reactions_url = build_activity_urls(profile_url)
    sections = [("Post", posts_url), ("Comment", comments_url), ("Like", reactions_url)]
    profile_slug = extract_profile_slug(profile_url)
    scroll_limit = INITIAL_SCROLL_LIMIT if is_historical else NORMAL_SCROLL_LIMIT

    for label, url in sections:
        try:
            goto(driver, url, wait_css_any=["body"], max_wait=45)
            human_sleep(5, 3)

            scroll_count = 0
            while scroll_count < scroll_limit:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                human_sleep(3.5, 2.0)
                scroll_count += 1

                current_count = sum(1 for r in results if r.get("type") == label)
                if current_count >= limit: break

            blocks = driver.find_elements(By.CSS_SELECTOR, "article, div.feed-shared-update-v2")
            if not blocks:
                blocks = driver.find_elements(By.XPATH, "//article|//div[contains(@class,'feed-shared-update')]")

            for b in blocks:
                if sum(1 for r in results if r.get("type") == label) >= limit: break

                item = None
                if label == "Post":
                    text = _extract_text_with_fallback(b)
                    if text: item = {"type": "Post", "text": text, "link": _extract_post_link(b) or url}
                elif label == "Comment":
                    try:
                        author_slug = _extract_post_author_slug(b)
                        # Skip comments made on user's own posts
                        if author_slug and author_slug.lower() == profile_slug.lower():
                            continue
                        post_snippet = _extract_text_with_fallback(b)
                        # For comments, keep only the target post snippet for cleaner output later
                        snippet = post_snippet[:400]
                        item = {"type": "Comment", "text": snippet, "link": _extract_post_link(b) or url}
                    except Exception: continue
                elif label == "Like":
                    author_slug = _extract_post_author_slug(b)
                    # Skip likes on user's own posts
                    if author_slug and author_slug.lower() == profile_slug.lower():
                        continue
                    post_snippet = _extract_text_with_fallback(b)
                    item = {"type": "Like", "text": post_snippet or "Liked a post.", "link": _extract_post_link(b) or url}

                if item:
                    sig = f"{item['type']}|{item['link']}|{item['text'][:50]}"
                    if sig not in {f"{r['type']}|{r['link']}|{r['text'][:50]}" for r in results}:
                        results.append(item)

        except Exception as e:
            logger.warning(f"Scrape section {label} failed for {profile_url}: {e}")

    return [r for r in results if r.get("text")]

def scrape_recent_post_texts(driver, profile_url: str, limit: int = 6, is_historical: bool = False) -> List[str]:
    all_url, _, _, _ = build_activity_urls(profile_url)
    goto(driver, all_url, wait_css_any=["body"], max_wait=45)
    human_sleep(5, 3)

    posts: List[str] = []
    scroll_count = 0
    scroll_limit = INITIAL_SCROLL_LIMIT if is_historical else NORMAL_SCROLL_LIMIT
    while len(posts) < limit and scroll_count < scroll_limit:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        human_sleep(3.5, 2.0)
        scroll_count += 1

        elements = driver.find_elements(By.XPATH, "//div[contains(@class,'update-components-text')]//span[@dir='ltr']")
        for p in elements:
            txt = safe_str((p.text or "").strip())
            if txt and txt not in posts:
                posts.append(txt)

    return posts[:limit]

# =========================
# LLM helpers (optional)
# =========================
def _extract_json_like(text: str) -> Optional[dict]:
    s = (text or "").strip()
    try: return json.loads(s)
    except Exception: pass
    try:
        m = re.search(r"\{.*\}", s, re.S)
        if m: return json.loads(m.group(0))
    except Exception: pass
    return None

def analyze_post(activity_text: str, past_posts: List[str], is_historical: bool = False) -> Dict[str, str]:
    fallback = {"summary": activity_text[:200], "themes": "['Not enough history']", "suggested_post": "(LLM unavailable)"}
    if not client: return fallback

    # Use different token limits and context based on analysis type
    max_tokens = MAX_TOKENS_HISTORICAL if is_historical else MAX_TOKENS_NORMAL
    max_context_posts = MAX_PAST_POSTS_HISTORICAL if is_historical else MAX_PAST_POSTS_NORMAL
    
    # Limit context posts to save tokens
    limited_past_posts = past_posts[:max_context_posts]
    
    # Truncate very long posts to save tokens
    truncated_text = activity_text[:800] if len(activity_text) > 800 else activity_text

    prompt = f"""Analyze the LinkedIn post. Return JSON with keys: "summary", "themes", "suggested_post".
New Post: {truncated_text}
Past Posts: {"\n".join(limited_past_posts)}"""

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL, 
            messages=[{"role": "user", "content": prompt}], 
            max_tokens=max_tokens, 
            temperature=0.5
        )
        content = resp.choices[0].message.content or ""
        data = _extract_json_like(content)
        if not isinstance(data, dict):
            return {"summary": content[:400], "themes": "['N/A']", "suggested_post": "N/A"}
        return {
            "summary": safe_str(data.get("summary", fallback["summary"])),
            "themes": safe_str(data.get("themes", fallback["themes"])),
            "suggested_post": safe_str(data.get("suggested_post", fallback["suggested_post"])),
        }
    except Exception as e:
        logger.warning(f"analyze_post failed with model '{OPENAI_MODEL}': {e}")
        # Attempt a single fallback model if configured
        try:
            if OPENAI_FALLBACK_MODEL and OPENAI_FALLBACK_MODEL != OPENAI_MODEL and client:
                resp = client.chat.completions.create(
                    model=OPENAI_FALLBACK_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1200,
                    temperature=0.5,
                )
                content = resp.choices[0].message.content or ""
                data = _extract_json_like(content)
                if not isinstance(data, dict):
                    return {"summary": content[:400], "themes": "['N/A']", "suggested_post": "N/A"}
                return {
                    "summary": safe_str(data.get("summary", fallback["summary"])),
                    "themes": safe_str(data.get("themes", fallback["themes"])),
                    "suggested_post": safe_str(data.get("suggested_post", fallback["suggested_post"]))
                }
        except Exception as e2:
            logger.warning(f"analyze_post fallback '{OPENAI_FALLBACK_MODEL}' failed: {e2}")
        return fallback

# =========================
# Message builder
# =========================
def build_grouped_message_for_profile(
    driver, profile_url: str, activities: List[Dict[str, str]], hashes_state: Dict[str, List[str]],
    global_hashes: List[str], report_index: int, report_total: int, is_historical: bool = False
) -> Optional[str]:
    profile_key = safe_str(profile_url)
    who_display = display_name_with_suffix(profile_url)
    slug = extract_profile_slug(profile_url)
    seen_hashes = list(hashes_state.get(profile_key, []))

    new_activities = []
    for act in activities:
        text = safe_str(act.get("text", ""))
        link = safe_str(act.get("link", "N/A"))
        typ = safe_str(act.get("type", "Post"))
        sig = f"{typ}|{link}|{text[:300]}"
        h = hashlib.md5(sig.encode()).hexdigest()
        # For historical run, include all activities; for normal run, only new ones
        if is_historical or h not in seen_hashes:
            act['hash'] = h
            new_activities.append(act)

    if not new_activities: return None

    timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
    run_type = "Historical Analysis" if is_historical else "Live Monitoring"
    lines = [
        f"📊 {run_type} Report {report_index}/{report_total} for <b>{html.escape(who_display)}</b>",
        f"🕒 {html.escape(timestamp)}\n",
        f"👤 Profile: <b>{html.escape(slug)}</b>",
        f"📅 Period: <b>{'Past 2 Months' if is_historical else 'New Activity'}</b>\n"
    ]

    past_posts = []
    if any(a['type'] == 'Post' for a in new_activities):
        try: 
            max_posts = MAX_PAST_POSTS_HISTORICAL if is_historical else MAX_PAST_POSTS_NORMAL
            past_posts = scrape_recent_post_texts(driver, profile_url, limit=max_posts, is_historical=is_historical)
        except Exception: pass

    # Group by type
    posts: List[Dict[str, str]] = [a for a in new_activities if a.get('type') == 'Post']
    comments: List[Dict[str, str]] = [a for a in new_activities if a.get('type') == 'Comment']
    likes: List[Dict[str, str]] = [a for a in new_activities if a.get('type') == 'Like']

    # 1) Posts
    if posts:
        lines.append("1) <b>Post Notification</b>")
        for idx, act in enumerate(posts, start=1):
            link = act['link']
            text = act['text']
            analysis = analyze_post(text, past_posts, is_historical=is_historical)
            lines.append(f"   {idx}) i) <b>Post Summary</b>: {html.escape(analysis['summary'])}")
            lines.append(f"      ii) <b>Recent Themes</b>: {html.escape(analysis['themes'])}")
            lines.append(f"      iii) <b>Suggestion</b>: {html.escape(analysis['suggested_post'])}")
            lines.append(f"      [Link: {html.escape(link)}]")
            lines.append("")
            if act['hash'] not in global_hashes:
                global_hashes.insert(0, act['hash'])
            seen_hashes.insert(0, act['hash'])

    # 2) Comments
    if comments:
        lines.append("2) <b>Comments Notification</b>")
        for idx, act in enumerate(comments, start=1):
            link = act['link']
            snippet = (act['text'][:200] + '…') if len(act['text']) > 200 else act['text']
            lines.append(f"   {idx}) 🗨️ {html.escape(snippet)}")
            lines.append(f"       [Link: {html.escape(link)}]")
            lines.append("")
            if act['hash'] not in global_hashes:
                global_hashes.insert(0, act['hash'])
            seen_hashes.insert(0, act['hash'])

    # 3) Likes
    if likes:
        lines.append("3) <b>Likes Notification</b>")
        for idx, act in enumerate(likes, start=1):
            link = act['link']
            snippet = (act['text'][:200] + '…') if len(act['text']) > 200 else act['text']
            lines.append(f"   {idx}) 👍 {html.escape(snippet)}")
            lines.append(f"       [Link: {html.escape(link)}]")
            lines.append("")
            if act['hash'] not in global_hashes:
                global_hashes.insert(0, act['hash'])
            seen_hashes.insert(0, act['hash'])

    hashes_state[profile_key] = seen_hashes[:50]
    return "\n".join(lines)

# =========================
# Token Usage Calculator
# =========================
def estimate_token_usage(num_users: int, posts_per_user: int, is_historical: bool = False) -> dict:
    """Estimate token usage and cost for analysis."""
    # Approximate token counts
    avg_post_length = 300  # characters
    avg_context_post_length = 200  # characters
    
    max_context_posts = MAX_PAST_POSTS_HISTORICAL if is_historical else MAX_PAST_POSTS_NORMAL
    max_tokens = MAX_TOKENS_HISTORICAL if is_historical else MAX_TOKENS_NORMAL
    
    # Per analysis
    input_tokens_per_analysis = (
        avg_post_length // 4 +  # Post text (~75 tokens)
        (avg_context_post_length * max_context_posts) // 4 +  # Context posts
        50  # Prompt overhead
    )
    output_tokens_per_analysis = max_tokens
    
    total_analyses = num_users * posts_per_user
    total_input_tokens = total_analyses * input_tokens_per_analysis
    total_output_tokens = total_analyses * output_tokens_per_analysis
    
    # Cost estimates (GPT-4o-mini pricing)
    input_cost_per_1k = 0.00015  # $0.00015 per 1K input tokens
    output_cost_per_1k = 0.0006   # $0.0006 per 1K output tokens
    
    total_cost = (
        (total_input_tokens / 1000) * input_cost_per_1k +
        (total_output_tokens / 1000) * output_cost_per_1k
    )
    
    return {
        "total_analyses": total_analyses,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "estimated_cost_usd": round(total_cost, 4),
        "per_analysis_cost": round(total_cost / total_analyses, 6) if total_analyses > 0 else 0
    }

# =========================
# Historical Analysis
# =========================
def is_first_run() -> bool:
    """Check if this is the first run by examining the state file."""
    if not os.path.exists(STATE_FILE):
        return True
    
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            # Check if state is empty or has no meaningful data
            hashes = state.get("hashes", {})
            global_hashes = state.get("global_hashes", [])
            return not hashes and not global_hashes
    except Exception:
        return True

def perform_historical_analysis(driver, hashes_state: Dict[str, List[str]], global_hashes: List[str]):
    """Perform initial historical analysis for all profiles."""
    logger.info("🔍 Performing initial historical analysis (past 2 months)...")
    send_telegram_html("🔍 <b>Starting Historical Analysis</b>\nFetching past 2 months of activity for all profiles...")
    
    historical_limit = 50  # Higher limit for historical data
    
    for idx, profile in enumerate(PROFILES, start=1):
        who = display_name_from_url(profile)
        logger.info(f"Historical analysis {idx}/{len(PROFILES)}: {who}")
        
        try:
            activities = scrape_profile_activity(driver, profile, limit=historical_limit, is_historical=True)
            msg = build_grouped_message_for_profile(
                driver, profile, activities, hashes_state, global_hashes, 
                idx, len(PROFILES), is_historical=True
            )
            
            if msg:
                logger.info(f"Historical data found for {who}, sending comprehensive report.")
                send_telegram_html(msg)
            else:
                logger.info(f"No historical activity found for {who}.")
                send_telegram_html(f"📭 No historical activity found for <b>{html.escape(who)}</b> in the past 2 months.")
            
            # Save state after each profile to preserve progress
            safe_save_json(STATE_FILE, {"hashes": hashes_state, "global_hashes": global_hashes[:500]})
            jitter_sleep(15, 30)  # Longer delays for historical scraping
            
        except Exception as e:
            logger.exception(f"Error in historical analysis for profile {profile}: {e}")
            send_telegram_html(f"⚠️ Historical analysis failed for <b>{html.escape(who)}</b>: {html.escape(safe_str(e))}")
    
    logger.info("✅ Historical analysis complete. Switching to normal monitoring mode.")
    send_telegram_html("✅ <b>Historical Analysis Complete!</b>\nNow switching to real-time monitoring mode.")

# =========================
# Main
# =========================
def main(run_once: bool = False):
    driver = None
    try:
        driver = build_driver()
        ensure_logged_in(driver)
    except Exception as e:
        logger.exception(f"Driver/login failed: {e}")
        send_telegram_html(f"<b>[FATAL] Login/Driver failed:</b> {html.escape(safe_str(e))}")
        if driver: driver.quit()
        return

    state = safe_load_json(STATE_FILE, default={"hashes": {}, "global_hashes": []})
    hashes_state = state.get("hashes", {})
    global_hashes = state.get("global_hashes", [])
    
    # Check if this is the first run
    if is_first_run():
        logger.info("🚀 First run detected! Starting historical analysis...")
        perform_historical_analysis(driver, hashes_state, global_hashes)
    else:
        send_telegram_html("🤖 <b>Bot started successfully!</b> Now monitoring LinkedIn for new activity...")

    try:
        while True:
            for idx, profile in enumerate(PROFILES, start=1):
                who = display_name_from_url(profile)
                logger.info(f"Scraping profile {idx}/{len(PROFILES)}: {who}")
                try:
                    activities = scrape_profile_activity(driver, profile, limit=6, is_historical=False)
                    msg = build_grouped_message_for_profile(
                        driver, profile, activities, hashes_state, global_hashes, 
                        idx, len(PROFILES), is_historical=False
                    )
                    if msg:
                        logger.info(f"Found new activity for {who}, sending notification.")
                        send_telegram_html(msg)
                    else:
                        logger.info(f"No new activity for {who}.")

                    safe_save_json(STATE_FILE, {"hashes": hashes_state, "global_hashes": global_hashes[:200]})
                    jitter_sleep(10, 25)
                except Exception as e:
                    logger.exception(f"Error scraping profile {profile}: {e}")
                    send_telegram_html(f"⚠️ Error scraping <b>{html.escape(who)}</b>: {html.escape(safe_str(e))}")

            if run_once:
                logger.info("Run-once mode: exiting after single cycle.")
                break

            logger.info("Cycle complete.")
            jitter_sleep(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)

    except KeyboardInterrupt:
        logger.info("Stopping gracefully...")
    except Exception:
        logger.exception("Unhandled exception in main loop")
    finally:
        if driver:
            driver.quit()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Activity Monitor")
    parser.add_argument("--once", action="store_true", help="Run a single monitoring cycle and exit.")
    args = parser.parse_args()

    try:
        logger.info("Starting LinkedIn monitor...")
        main(run_once=True)
    except Exception as e:
        logger.exception(f"[FATAL] Unhandled exception: {e}")
        raise
