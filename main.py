import asyncio
import struct
import base64
import json
import httpx
import aiohttp
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser

# ==================== CREDENTIALS ====================
ACCOUNT1 = {
    "MY_USER_ID": "704772337",
    "AUTH_TOKEN": "000109a238c22edaed3918aacb3d8c0a4360d480",
    "CT0":        "6fd94ab6e318068f4e34c27c07d5b055541c8447ddc43e14d8ac0cedbe02a6efb5060c89092b47d6e071e61aca37496f44886a1c141abc20bb5aec817f214dcd2fbc7f22f39372ab5a8664ecb553f439",
    "LABEL":      "1",
}
ACCOUNT2 = {
    "MY_USER_ID": "2050569848002957312",
    "AUTH_TOKEN": "52374ce131bffe2766c9878c792f5e0074a200a1",
    "CT0":        "e0c6dab0995fa9426c647337b5b16678b75852d196a688526489efcfe924ed5cb288e87d5b43562e529f33af770670115413b85aa4f7f3b0f9edec945ab7f62811b4fafb8125de79722be7d8dc7e9e4c",
    "LABEL":      "2",
}

BEARER_TOKEN     = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
TELEGRAM_TOKEN   = "8630469503:AAHqID7tpgZ49_p_DgfIIhgt5CkBPO_MkQo"
TELEGRAM_CHAT_ID = "6607397366"
USER_AGENT       = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:155.0) Gecko/20100101 Firefox/155.0"
HEARTBEAT_B64    = "DAACDAACAAAA"
PRESENCE_TIMEOUT = 20  
XCHAT_PASSCODE   = "0807"
BROWSERLESS_KEY  = "2VJ6TPwl5gUfRJ6d0f0b13100be31ef626d653ea91f852dc4"

# ==================== USER ID FILTERS ====================
TARGET_USER_ID = "1885488902670000129"
REEM_USER_ID   = "954222428791681025"
NOORA_USER_ID  = "2082060317358743552"
JAMILA_USER_ID = "2024978767081254912"

# ============================================================
# HELPERS
# ============================================================

def now() -> str:
    return datetime.now().strftime("%H:%M:%S")

def get_label(sender_id: str) -> str:
    return {
        TARGET_USER_ID: "Target",
        REEM_USER_ID:   "Reem",
        NOORA_USER_ID:  "Noora",
        JAMILA_USER_ID: "Jamila",
    }.get(sender_id, "Someone")

def get_account_by_id(my_id: str) -> dict:
    return ACCOUNT1 if my_id == ACCOUNT1["MY_USER_ID"] else ACCOUNT2

# ============================================================
# PRESENCE
# ============================================================

_presence: dict = {}

def mark_presence(conv_id: str) -> None:
    loop = asyncio.get_event_loop()
    old  = _presence.get(conv_id)
    if old: old.cancel()
    def expire(): _presence.pop(conv_id, None)
    _presence[conv_id] = loop.call_later(PRESENCE_TIMEOUT, expire)

def is_muted(conv_id: str) -> bool:
    return conv_id in _presence

# ============================================================
# TELEGRAM SETUP & FUNCTIONS
# ============================================================

def get_menu_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🎯 Target (Acc 1)", "callback_data": "target"}, {"text": "🎯 Target (Acc 2)", "callback_data": "target2"}],
            [{"text": "🌸 Reem (Acc 1)", "callback_data": "reem"}, {"text": "🌸 Reem (Acc 2)", "callback_data": "reem2"}],
            [{"text": "🌺 Noora (Acc 1)", "callback_data": "noora"}, {"text": "🌺 Noora (Acc 2)", "callback_data": "noora2"}],
            [{"text": "🌼 Jamila (Acc 1)", "callback_data": "jamila"}, {"text": "🌼 Jamila (Acc 2)", "callback_data": "jamila2"}]
        ]
    }

async def set_bot_commands() -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands"
    commands = [
        {"command": "start", "description": "Open Options Menu"},
        {"command": "menu", "description": "Open Options Menu"},
    ]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json={"commands": commands})
        print(f"[{now()}] 🤖 Telegram command menu registered")
    except Exception as e:
        print(f"[{now()}] ⚠️ Failed to set Telegram commands: {e}")

async def send_telegram(title: str, message: str, show_keyboard: bool = False) -> None:
    text = f"*{title}*\n{message}"
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown",
    }
    
    if show_keyboard:
        payload["reply_markup"] = get_menu_keyboard()

    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.post(url, json=payload)
            if r.is_success:
                return
        except Exception as e:
            print(f"[{now()}] Telegram attempt {attempt}/3 failed: {e}")
        if attempt < 3:
            await asyncio.sleep(2 * attempt)

async def send_telegram_photo(caption: str, image_bytes: bytes) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(url, data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": caption,
                    "reply_markup": json.dumps(get_menu_keyboard())
                }, files={
                    "photo": ("msg.png", image_bytes, "image/png"),
                })
            if r.is_success:
                print(f"[{now()}] ✅ Photo sent to Telegram")
                return
            else:
                print(f"[{now()}] ⚠️ Telegram photo HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[{now()}] Telegram photo attempt {attempt}/3 failed: {e}")
        if attempt < 3:
            await asyncio.sleep(2 * attempt)

# ============================================================
# BROWSER / DOM MESSAGE READER
# ============================================================

_pw_instance       = None
_browser: Browser  = None
_pages: dict       = {}   # (conv_id, account_label) -> Page
_last_id: dict     = {}   # (conv_id, account_label) -> last message id
_opening: dict     = {}   # (conv_id, account_label) -> asyncio.Event
_page_lock         = asyncio.Lock()

async def ensure_browser():
    """Connects/reconnects to Browserless with plan-compliant timeout limit (120000ms)."""
    global _pw_instance, _browser, _pages, _opening
    
    if _pw_instance is None:
        _pw_instance = await async_playwright().start()

    if _browser is None or not _browser.is_connected():
        if _browser is not None:
            print(f"[{now()}] 🔄 Connection lost. Reconnecting to Browserless...")
            
        _pages.clear()
        _opening.clear()
        
        # Max plan timeout allowed by Browserless is 120000ms (2 minutes)
        ws_endpoint = f"wss://chrome.browserless.io?token={BROWSERLESS_KEY}&timeout=120000&keepalive=true"
        _browser = await _pw_instance.chromium.connect_over_cdp(ws_endpoint)
        print(f"[{now()}] ✅ Connected to Browserless successfully")

async def open_chat(conv_id: str, account: dict) -> Page:
    await ensure_browser()
    
    key       = (conv_id, account["LABEL"])
    dash_conv = conv_id.replace(":", "-")
    print(f"[{now()}] 📂 Opening chat: {dash_conv} [Acc{account['LABEL']}]")

    mark_presence(conv_id)

    page = await _browser.new_page(viewport={"width": 1400, "height": 900})
    await page.set_extra_http_headers({"User-Agent": USER_AGENT})

    await page.context.add_cookies([
        {"name": "auth_token", "value": account["AUTH_TOKEN"], "domain": ".x.com", "path": "/"},
        {"name": "ct0",        "value": account["CT0"],        "domain": ".x.com", "path": "/"},
    ])

    await page.goto(f"https://x.com/i/chat/{dash_conv}", wait_until="load", timeout=60000)

    try:
        await page.wait_for_selector("input[inputmode='numeric']", timeout=8000)
        for digit in XCHAT_PASSCODE:
            await page.keyboard.type(digit)
            await asyncio.sleep(0.15)
        await page.keyboard.press("Enter")
        print(f"[{now()}] 🔑 PIN entered for {dash_conv}")
    except Exception:
        pass

    await page.wait_for_selector("[data-testid='dm-composer-textarea']", timeout=30000)

    await page.wait_for_function("""
        () => {
            const msgs = document.querySelectorAll('[data-testid^="message-text-"]');
            for (const m of msgs) {
                if (m.innerText && m.innerText.trim().length > 0) return true;
            }
            return false;
        }
    """, timeout=30000)

    def cleanup():
        _pages.pop(key, None)
        print(f"[{now()}] ⚠️ Page closed: {dash_conv} [Acc{account['LABEL']}]")

    page.on("close", lambda: cleanup())
    page.on("crash", lambda: cleanup())

    _pages[key] = page
    mark_presence(conv_id)
    print(f"[{now()}] ✅ Chat ready: {dash_conv} [Acc{account['LABEL']}]")
    return page

async def get_latest_screenshot(conv_id: str, account: dict, force: bool = False):
    key = (conv_id, account["LABEL"])

    async with _page_lock:
        if key not in _pages:
            if key not in _opening:
                _opening[key] = asyncio.Event()
                try:
                    await open_chat(conv_id, account)
                except Exception as e:
                    print(f"[{now()}] ❌ Failed to open chat {conv_id} [Acc{account['LABEL']}]: {e}")
                    return None, None
                finally:
                    ev = _opening.pop(key, None)
                    if ev: ev.set()
            else:
                await _opening[key].wait()

    page = _pages.get(key)
    if not page:
        return None, None

    known_id = _last_id.get(key, "")

    async def close_page():
        try:
            await page.close()
        except Exception:
            pass
        _pages.pop(key, None)
        print(f"[{now()}] 🗑️ Tab closed: {conv_id} [Acc{account['LABEL']}]")

    async def schedule_close():
        await asyncio.sleep(110) # Auto-cleanup shortly before Browserless 120s limit
        await close_page()

    asyncio.create_task(schedule_close())

    if force:
        try:
            mark_presence(conv_id)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.3)
            screenshot = await page.screenshot(type="png", full_page=False)
            print(f"[{now()}] 📸 Force screenshot taken")
            return screenshot, known_id
        except Exception as e:
            print(f"[{now()}] ❌ Force screenshot failed: {e}")
            return None, None

    try:
        result = await page.wait_for_function(
            """(knownId) => {
                const els = document.querySelectorAll('[data-testid^="message-text-"]');
                if (!els.length) return null;
                const last = els[els.length - 1];
                const id   = last.getAttribute('data-testid');
                if (id !== knownId) return id;
                return null;
            }""",
            arg=known_id,
            timeout=15000,
        )
        new_id = await result.json_value()
        if not new_id:
            return None, None

        _last_id[key] = new_id

        mark_presence(conv_id)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        await page.wait_for_function(
            """(msgId) => {
                const el = document.querySelector('[data-testid="' + msgId + '"]');
                if (!el) return true;
                let bubble = el;
                for (let i = 0; i < 10; i++) {
                    if (!bubble.parentElement) break;
                    bubble = bubble.parentElement;
                    const tag = bubble.tagName.toLowerCase();
                    if (tag === 'li' || tag === 'article') break;
                }
                const imgs = Array.from(bubble.querySelectorAll('img'));
                const content = imgs.filter(img => {
                    const r = img.getBoundingClientRect();
                    return r.width > 16 && r.height > 16;
                });
                if (!content.length) return true;
                return content.every(img => img.complete && img.naturalWidth > 0);
            }""",
            arg=new_id,
            timeout=12000,
        )

        mark_presence(conv_id)
        screenshot = await page.screenshot(type="png", full_page=False)
        print(f"[{now()}] 📸 Screenshot taken for {new_id}")
        return screenshot, new_id

    except Exception as e:
        print(f"[{now()}] ⚠️ Screenshot failed: {e} - shooting anyway")
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            screenshot = await page.screenshot(type="png", full_page=False)
            return screenshot, known_id
        except Exception as e2:
            print(f"[{now()}] ❌ Fallback screenshot failed: {e2}")
            return None, None

# ============================================================
# THRIFT PARSER
# ============================================================

def parse_thrift(buf: bytes, offset: int):
    fields = {}
    while offset < len(buf):
        if offset + 3 > len(buf): break
        type_id = buf[offset]
        field   = struct.unpack_from(">H", buf, offset + 1)[0]
        offset += 3
        if type_id == 0: break
        if type_id == 11:
            if offset + 4 > len(buf): break
            ln = struct.unpack_from(">I", buf, offset)[0]; offset += 4
            if offset + ln > len(buf): break
            fields[field] = buf[offset:offset+ln].decode("utf-8", errors="replace"); offset += ln
        elif type_id == 12:
            inner, offset = parse_thrift(buf, offset); fields[field] = inner
        elif type_id == 15:
            if offset + 5 > len(buf): break
            et = buf[offset]; offset += 1
            cnt = struct.unpack_from(">I", buf, offset)[0]; offset += 4
            lst = []
            for _ in range(cnt):
                if et == 12:
                    inner, offset = parse_thrift(buf, offset); lst.append(inner)
                elif et == 11:
                    if offset + 4 > len(buf): break
                    ln = struct.unpack_from(">I", buf, offset)[0]; offset += 4
                    if offset + ln > len(buf): break
                    lst.append(buf[offset:offset+ln].decode("utf-8", errors="replace")); offset += ln
                else: break
            fields[field] = lst
        elif type_id == 10:
            if offset + 8 > len(buf): break
            hi, lo = struct.unpack_from(">II", buf, offset)
            fields[field] = hi * 4_294_967_296 + lo; offset += 8
        elif type_id == 8:
            if offset + 4 > len(buf): break
            fields[field] = struct.unpack_from(">i", buf, offset)[0]; offset += 4
        elif type_id == 2:
            if offset >= len(buf): break
            fields[field] = buf[offset]; offset += 1
        else: break
    return fields, offset

# ============================================================
# FRAME PARSERS
# ============================================================

def try_parse_seen(buf):
    try:
        root, _ = parse_thrift(buf, 0)
        outer = root.get(1)
        if not outer: return None
        rid = str(outer.get(3, ""))
        if not rid.isdigit() or not (6 <= len(rid) <= 20): return None
        cid = str(outer.get(4, ""))
        if ":" not in cid: return None
        f7 = outer.get(7)
        if not f7: return None
        f12 = f7.get(12)
        if not f12 or not f12.get(1) or not f12.get(2): return None
        return {"reader_id": rid, "conv_id": cid}
    except: return None

def try_parse_message(buf):
    try:
        root, _ = parse_thrift(buf, 0)
        outer = root.get(1)
        if not outer: return None
        sid = str(outer.get(3, ""))
        if not sid.isdigit() or not (6 <= len(sid) <= 20): return None
        cid = str(outer.get(4, ""))
        if ":" not in cid: return None
        f7 = outer.get(7)
        if not f7: return None
        f1 = f7.get(1)
        if not f1 or f1.get(102) != 1: return None
        mid = outer.get(1)
        if not mid or not f1.get(104): return None
        return {"sender_id": sid, "conv_id": cid, "msg_id": str(mid)}
    except: return None

# ============================================================
# TYPING STATE
# ============================================================

_typing_flags:  dict = {}
_typing_timers: dict = {}

async def on_typing(label: str, key: str, acct_label: str) -> None:
    loop = asyncio.get_event_loop()
    if not _typing_flags.get(key):
        _typing_flags[key] = True
        if not is_muted(key):
            print(f"[{now()}] ⌨️  [Acc{acct_label}] {label} is typing...")
    old = _typing_timers.get(key)
    if old: old.cancel()
    def stop(): _typing_flags[key] = False
    _typing_timers[key] = loop.call_later(4.0, stop)

# ============================================================
# HANDLE FRAME
# ============================================================

async def handle_frame(buf: bytes, account: dict) -> None:
    lbl   = account["LABEL"]
    my_id = account["MY_USER_ID"]

    seen = try_parse_seen(buf)
    if seen:
        if seen["reader_id"] == my_id:
            mark_presence(seen["conv_id"])
            return
        if is_muted(seen["conv_id"]): return
        name = get_label(seen["reader_id"])
        print(f"[{now()}] 👁️  [Acc{lbl}] {name} SEEN")
        return

    msg = try_parse_message(buf)
    if msg:
        sid = msg["sender_id"]
        if sid == my_id:
            mark_presence(msg["conv_id"])
            return
        if my_id not in msg["conv_id"].split(":"): return
        if is_muted(msg["conv_id"]): return
        name = get_label(sid)
        print(f"[{now()}] 💬 [Acc{lbl}] {name} - new message detected")
        return

    try:
        cleaned  = "".join(c if 0x20 <= ord(c) <= 0x7E else " "
                           for c in buf.decode("utf-8", errors="replace")).strip()
        typer_id = cleaned.split()[1] if len(cleaned.split()) > 1 else ""
    except: return

    if not typer_id or not typer_id.isdigit() or not (6 <= len(typer_id) <= 20): return
    if typer_id == my_id:
        mark_presence(typer_id)
        return
    if is_muted(typer_id): return
    await on_typing(get_label(typer_id), typer_id, lbl)

# ============================================================
# FETCH WS TOKEN
# ============================================================

async def fetch_ws_url(account: dict) -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            "https://api.x.com/graphql/Qh3fZRjPPtPoHYR_2sCZsA/GenerateXChatTokenMutation",
            headers={
                "User-Agent":    USER_AGENT,
                "Accept":        "application/json",
                "Content-Type":  "application/json",
                "x-csrf-token":  account["CT0"],
                "authorization": BEARER_TOKEN,
                "Cookie":        f"auth_token={account['AUTH_TOKEN']}; ct0={account['CT0']};",
                "Origin":        "https://x.com",
                "Referer":       "https://x.com/",
            },
            content=json.dumps({"variables": {}}).encode(),
        )
    if not r.is_success:
        raise RuntimeError(f"Token fetch failed: HTTP {r.status_code}")
    data  = r.json()
    token = (
        (data.get("data") or {}).get("user_get_x_chat_auth_token", {}).get("token")
        or data.get("user_get_x_chat_auth_token", {}).get("token")
    )
    if not token:
        raise RuntimeError("Token not found in response")
    return f"wss://chat-ws.x.com/ws?token={token}"

# ============================================================
# MONITOR
# ============================================================

async def monitor(account: dict) -> None:
    tag     = f"[Acc{account['LABEL']}]"
    attempt = 0

    while True:
        attempt += 1
        backoff = min(2 ** (attempt - 1), 60)

        try:
            ws_url = await fetch_ws_url(account)
            connector = aiohttp.TCPConnector(force_close=False, enable_cleanup_closed=True)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.ws_connect(
                    ws_url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Origin":     "https://x.com",
                        "Cookie":     f"auth_token={account['AUTH_TOKEN']}; ct0={account['CT0']};",
                    },
                    receive_timeout=90,
                    autoclose=True,
                    autoping=True,
                ) as ws:
                    print(f"[{now()}] 🟢 {tag} CONNECTED")
                    await asyncio.sleep(1)
                    attempt = 0

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.BINARY:
                            buf = msg.data
                            if base64.b64encode(buf).decode() == HEARTBEAT_B64:
                                continue
                            await handle_frame(buf, account)
                        elif msg.type == aiohttp.WSMsgType.TEXT:
                            await handle_frame(msg.data.encode(), account)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                            print(f"[{now()}] 🔴 {tag} WS closed - reconnecting in {backoff}s")
                            break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print(f"[{now()}] ❌ {tag} WS error - reconnecting in {backoff}s")
                            break

        except asyncio.TimeoutError:
            print(f"[{now()}] ⏱ {tag} Timeout - reconnecting in {backoff}s")
        except Exception as e:
            print(f"[{now()}] ❌ {tag} {type(e).__name__}: {e} - reconnecting in {backoff}s")

        await asyncio.sleep(backoff)

# ============================================================
# TELEGRAM COMMAND POLLING
# ============================================================

COMMAND_MAP = {
    "target":   [(f"{ACCOUNT1['MY_USER_ID']}:{TARGET_USER_ID}",  ACCOUNT1)],
    "target2":  [(f"{ACCOUNT2['MY_USER_ID']}:{TARGET_USER_ID}",  ACCOUNT2)],
    "reem":     [(f"{ACCOUNT1['MY_USER_ID']}:{REEM_USER_ID}",    ACCOUNT1)],
    "reem2":    [(f"{ACCOUNT2['MY_USER_ID']}:{REEM_USER_ID}",    ACCOUNT2)],
    "noora":    [(f"{ACCOUNT1['MY_USER_ID']}:{NOORA_USER_ID}",   ACCOUNT1)],
    "noora2":   [(f"{ACCOUNT2['MY_USER_ID']}:{NOORA_USER_ID}",   ACCOUNT2)],
    "jamila":   [(f"{ACCOUNT1['MY_USER_ID']}:{JAMILA_USER_ID}",  ACCOUNT1)],
    "jamila2":  [(f"{ACCOUNT2['MY_USER_ID']}:{JAMILA_USER_ID}",  ACCOUNT2)],
}

async def telegram_poll() -> None:
    offset = 0
    url_get = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    url_ans = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    print(f"[{now()}] 🤖 Telegram command polling started")

    while True:
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                r = await client.get(url_get, params={
                    "offset":          offset,
                    "timeout":         30,
                    "allowed_updates": ["message", "callback_query"],
                })
            if not r.is_success:
                await asyncio.sleep(5)
                continue

            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                
                cmd = None
                chat_id = None
                
                if "callback_query" in update:
                    cb = update["callback_query"]
                    chat_id = str(cb.get("message", {}).get("chat", {}).get("id"))
                    cmd = cb.get("data", "").strip().lower()
                    
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.post(url_ans, json={"callback_query_id": cb.get("id")})

                elif "message" in update:
                    msg = update["message"]
                    chat_id = str(msg.get("chat", {}).get("id"))
                    text = (msg.get("text") or "").strip().lower()
                    if text.startswith("/"):
                        text = text[1:]
                    cmd = text

                if chat_id != TELEGRAM_CHAT_ID or not cmd:
                    continue

                print(f"[{now()}] 🤖 Command received: {cmd}")

                if cmd in ["start", "menu"]:
                    await send_telegram("Bot Menu", "Select an account to screenshot:", show_keyboard=True)
                    continue

                entries = COMMAND_MAP.get(cmd)
                if not entries:
                    await send_telegram("Bot", f"Unknown command: {cmd}\nPlease use the menu below:", show_keyboard=True)
                    continue

                sent = False
                for conv_id, account in entries:
                    try:
                        key    = (conv_id, account["LABEL"])
                        force  = key in _pages
                        screenshot, _ = await get_latest_screenshot(conv_id, account, force=force)
                        if screenshot:
                            await send_telegram_photo(f"{cmd.capitalize()} {account['LABEL']}", screenshot)
                            sent = True
                            break
                    except Exception as e:
                        print(f"[{now()}] ⚠️ Command screenshot failed [Acc{account['LABEL']}]: {e}")

                if not sent:
                    await send_telegram("Bot", f"Could not capture {cmd.capitalize()}'s chat", show_keyboard=True)

        except Exception as e:
            print(f"[{now()}] ⚠️ Telegram poll error: {e}")
            await asyncio.sleep(5)

# ============================================================
# ENTRY POINT
# ============================================================

async def main():
    await set_bot_commands()
    await send_telegram("🟢 Bot Online", "Select an account to view:", show_keyboard=True)
    await ensure_browser()
    await asyncio.gather(
        monitor(ACCOUNT1),
        monitor(ACCOUNT2),
        telegram_poll(),
        return_exceptions=True,
    )

if __name__ == "__main__":
    asyncio.run(main())
