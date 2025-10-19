# monitor_terms.py
import os
import time
import json
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests

load_dotenv()

# Налаштування з .env
URL = os.getenv("TARGET_URL", "https://portal.minv.sk/wps/portal/domov/ecu/ecu_elektronicke_sluzby/ecu-vysys/!ut/p/a1/...")
STATE_FILE = Path(os.getenv("STATE_FILE", "state.json"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SEC", "3600"))  # сікунди між перевірками (cron краще для production)

# Telegram
TG_TOKEN = os.getenv("TG_TOKEN")        # токен бота
TG_CHAT_ID = os.getenv("TG_CHAT_ID")    # твій chat_id)    

# CSS selector або XPATH до блоку з термінами
# <- тут треба вказати точний селектор після того, як знайдеш у сторінці
ITEM_SELECTOR = os.getenv("ITEM_SELECTOR", "div.some-class .term-item")  # приклад, заміни під свій сайт

# === допоміжні функції ===
def send_telegram_message(text):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, data=payload, timeout=10)
    print("Telegram response:", r.status_code, r.text)

def load_state():
    if not STATE_FILE.exists():
        return {"items": []}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

# Парсинг сторінки (через Selenium)
def fetch_page_source(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    from selenium.webdriver.chrome.service import Service
    service = Service(r"D:\driverchrome\chromedriver.exe")



    driver = webdriver.Chrome(service=service, options=chrome_options)
    try:
        print("Loading page...", url)
        driver.get(url)
        time.sleep(2)
        return driver.page_source
    finally:
        driver.quit()


# Видобування елементів
def parse_terms(html):
    soup = BeautifulSoup(html, "lxml")
    items = []
    # Спробуй знайти елементи за селектором або адаптуй нижче вручну
    found = soup.select(ITEM_SELECTOR)
    if not found:
        # Якщо селектор не знайшов — спробуй знайти релевантні блоки за ключовими словами
        # Наприклад: шукаємо таблиці або div-елементи з текстом "term" або "dátum" тощо
        candidates = soup.find_all(text=lambda t: t and ("term" in t.lower() or "dátum" in t.lower() or "lehot" in t.lower()))
        for c in candidates:
            parent = c.find_parent()
            if parent:
                items.append(parent.get_text(strip=True))
    else:
        for el in found:
            text = el.get_text(" ", strip=True)
            items.append(text)
    # Унікалізація
    unique = []
    for it in items:
        if it not in unique:
            unique.append(it)
    return unique

def compare_and_notify(old_items, new_items):
    old_set = set(old_items)
    new_set = set(new_items)
    added = [x for x in new_items if x not in old_set]
    removed = [x for x in old_items if x not in new_set]
    if added or removed:
        msg_lines = [f"Changes detected on {URL} at {datetime.utcnow().isoformat()} (UTC)"]
        if added:
            msg_lines.append("\nNew items:")
            for a in added:
                msg_lines.append("- " + a)
        if removed:
            msg_lines.append("\nRemoved items:")
            for r in removed:
                msg_lines.append("- " + r)
        message = "\n".join(msg_lines)
        print(message)
        send_telegram_message(message)
    else:
        print("No changes detected.")

def main_once():
    html = fetch_page_source(URL)
    items = parse_terms(html)
    state = load_state()
    old_items = state.get("items", [])
    compare_and_notify(old_items, items)
    # збережемо новий стан
    state["items"] = items
    state["last_checked"] = datetime.utcnow().isoformat()
    save_state(state)
if __name__ == "__main__":
    send_telegram_message("✅ Тест: бот підключений і працює!")  # тестове повідомлення
    while True:
        main_once()
        time.sleep(CHECK_INTERVAL)

    # Для початку просто виконай один запуск
  
