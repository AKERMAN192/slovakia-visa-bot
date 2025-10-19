# monitor_terms.py
import os
import time
import json
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Вимикаємо SSL-попередження
warnings.simplefilter('ignore', InsecureRequestWarning)

# === Налаштування ===
load_dotenv()

BASE_URL = os.getenv("TARGET_URL", "https://portal.minv.sk/wps/portal/domov/ecu/ecu_elektronicke_sluzby/ecu-vysys/!ut/p/a1/pZJNDoIwEEbP4gn6tZZCl60_bVEkqERlY1gZEkUXxvMLRBdorCbObpL3ZjozJQXZkqIub9WhvFbnujy2eSH2HKOJjWeIjVRDZEIzFaQpAN4AuwbAh1Do-1gGU2TUWJ0YMHD28D1Az4_suik6mwZWZoshDH3134GenyZUQOXJWiuZM5jn-0dGWR7O24kiBjfWdhzKBHDit_k9Df7yEfzpf-2_IUWHUMYc1asGiTIJZZwI2URTRPQL4PAAfDvsAN8n8Z6p3YIf4ORyyrvYonKVU4M7UEEQug!!/dl5/d5/L2dBISEvZ0FBIS9nQSEh/")
STATE_FILE = Path(os.getenv("STATE_FILE", "state.json"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SEC", "1800"))

TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# === Міста ===
CITIES = {
    "Bratislava": BASE_URL,
    "Košice": BASE_URL,
    "Nitra": BASE_URL,
    "Žilina": BASE_URL,
}

# === Telegram ===
def send_telegram_message(text):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        print("Telegram response:", r.status_code)
    except Exception as e:
        print("Telegram send failed:", e)


# === Завантаження сторінки ===
def fetch_page_source(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0.0.0 Safari/537.36"
    }

    for attempt in range(3):
        try:
            print(f"Attempt {attempt + 1} to fetch {url}")
            response = requests.get(url, timeout=15, headers=headers, verify=False)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(5)
    return None


# === Парсинг термінів ===
def parse_terms(html):
    soup = BeautifulSoup(html, "lxml")
    items = []
    candidates = soup.find_all(
        text=lambda t: t and ("term" in t.lower() or "dátum" in t.lower() or "voľný" in t.lower())
    )
    for c in candidates:
        parent = c.find_parent()
        if parent:
            text = parent.get_text(" ", strip=True)
            if text not in items:
                items.append(text)
    return items


# === Стан збереження ===
def load_state():
    if not STATE_FILE.exists():
        return {"cities": {}, "site_down": False}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# === Основна логіка ===
def main_once():
    state = load_state()
    new_state = {"cities": {}, "site_down": state.get("site_down", False)}

    site_down = False

    for city, url in CITIES.items():
        print(f"\n🔍 Перевірка міста {city}...")

        html = fetch_page_source(url)
        if not html:
            site_down = True
            continue  # переходимо до наступного міста

        terms = parse_terms(html)
        new_state["cities"][city] = terms

        old_terms = state.get("cities", {}).get(city, [])
        new_terms = [t for t in terms if t not in old_terms]

        if new_terms:
            msg = f"📅 <b>Нові терміни у {city}:</b>\n" + "\n".join(f"• {t}" for t in new_terms)
            send_telegram_message(msg)
        else:
            print(f"Немає нових термінів для {city}.")

    # === Повідомлення про стан сайту ===
    if site_down and not state.get("site_down", False):
        send_telegram_message("⚠️ Сайт portal.minv.sk не відповідає. Перевір, чи він працює.")
    elif not site_down and state.get("site_down", False):
        send_telegram_message("✅ Сайт portal.minv.sk знову працює!")

    new_state["site_down"] = site_down
    save_state(new_state)
    print("\n✅ Перевірка завершена.")


# === Безкінечний цикл ===
if __name__ == "__main__":
    while True:
        main_once()
        print(f"🕒 Наступна перевірка через {CHECK_INTERVAL} секунд...\n{'-'*50}")
        time.sleep(CHECK_INTERVAL)
