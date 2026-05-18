"""
╔══════════════════════════════════════════════════════════════╗
║        PyTube Player  +  Google AI Video Explainer           ║
║                                                              ║
║  ALL APIs from Google Cloud Console:                         ║
║   • YouTube Data API v3      — search & video info           ║
║   • Gemini 1.5 Flash API     — AI video explanation          ║
║   • Cloud Translation API v2 — translate to Hindi/Hinglish   ║
║                                                              ║
║  Languages: Hindi | English | Hinglish (Hindi+English mix)   ║
╚══════════════════════════════════════════════════════════════╝

ONE KEY DOES EVERYTHING:
  → https://console.cloud.google.com
  → Create/Select a project
  → Enable these 3 APIs:
      1. YouTube Data API v3
      2. Generative Language API  (Gemini)
      3. Cloud Translation API
  → Credentials → Create API Key → paste below or enter in app

INSTALL:
  pip install customtkinter Pillow requests

RUN:
  python youtube_player.py
"""

import threading
import webbrowser
import re
import json
from io import BytesIO
import tkinter as tk
import tkinter.messagebox as messagebox

try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit("  pip install customtkinter")

try:
    from PIL import Image, ImageTk
except ImportError:
    raise SystemExit("  pip install Pillow")

try:
    import requests
except ImportError:
    raise SystemExit("pip install requests")

# ════════════════════════════════════════════════════════
#   ONE Google API Key for everything (or enter in app)
GOOGLE_API_KEY = ""    # e.g. "AIzaSy..."
# ════════════════════════════════════════════════════════

# ── Google API Endpoints ─────────────────────────────────
YT_SEARCH_URL   = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS_URL   = "https://www.googleapis.com/youtube/v3/videos"
YT_CHANNEL_URL  = "https://www.googleapis.com/youtube/v3/channels"
# Gemini endpoints — we try v1 first (stable), fall back to v1beta
GEMINI_BASE_V1    = "https://generativelanguage.googleapis.com/v1/models"
GEMINI_BASE_BETA  = "https://generativelanguage.googleapis.com/v1beta/models"
# Fallback model IDs tried in order (correct 2025 names)
GEMINI_MODELS = [
    "gemini-2.0-flash-001",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite-001",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-002",
    "gemini-1.5-flash",
    "gemini-1.5-pro-001",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
]
TRANSLATE_URL   = "https://translation.googleapis.com/language/translate/v2"

# ── Theme ────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

RED      = "#FF0000"
DARK_BG  = "#0A0A0A"
CARD_BG  = "#1A1A1A"
AI_PANEL = "#0D0D1F"
HOVER_BG = "#2A2A2A"
WHITE    = "#FFFFFF"
GREY     = "#AAAAAA"
LGREY    = "#666666"
GREEN    = "#00C853"
ACCENT   = "#4285F4"   # Google Blue
GEMINI   = "#8AB4F8"   # Gemini light blue
THUMB_W  = 220
THUMB_H  = 124

LANGUAGES = {
    "🇮🇳 Hinglish": "hinglish",
    "🇮🇳 Hindi":    "hi",
    "🇬🇧 English":  "en",
    "🇯🇵 Japanese": "ja",
    "🇫🇷 French":   "fr",
    "🇩🇪 German":   "de",
    "🇪🇸 Spanish":  "es",
    "🇧🇩 Bengali":  "bn",
    "🇵🇰 Urdu":     "ur",
    "🇮🇳 Tamil":    "ta",
    "🇮🇳 Telugu":   "te",
}


# ═══════════════════════════════════════════════════════════
#  Google API Helpers
# ═══════════════════════════════════════════════════════════

def yt_get(url: str, params: dict, api_key: str) -> dict:
    p = dict(params)
    p["key"] = api_key
    r = requests.get(url, params=p, timeout=12)
    r.raise_for_status()
    return r.json()


def list_gemini_models(api_key: str) -> list:
    """Fetch available Gemini models that support generateContent.
    Tries v1 (stable) then v1beta. Returns [] on failure but prints reason."""
    for base in [GEMINI_BASE_V1, GEMINI_BASE_BETA]:
        try:
            r = requests.get(base, params={"key": api_key}, timeout=12)
            if r.status_code == 200:
                models = r.json().get("models", [])
                found = [
                    m["name"].split("/")[-1]
                    for m in models
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                    and "gemini" in m.get("name", "").lower()
                ]
                if found:
                    print(f"[Gemini] Available models from {base}:\n  " + "\n  ".join(found))
                    return found
        except Exception as e:
            print(f"[Gemini] ListModels failed on {base}: {e}")
    return []


def gemini_explain(api_key: str, video_info: dict, lang_label: str, lang_code: str) -> str:
    """Call Gemini API with auto model detection — tries available models in order."""

    title    = video_info.get("title", "Unknown")
    channel  = video_info.get("channel", "Unknown")
    desc     = video_info.get("description", "")[:1500]
    views    = video_info.get("views", "N/A")
    likes    = video_info.get("likes", "N/A")
    duration = video_info.get("duration", "N/A")
    tags     = ", ".join(video_info.get("tags", [])[:12]) or "N/A"

    if lang_code == "hinglish":
        lang_instruction = (
            "Explain this YouTube video in **Hinglish** — "
            "a natural mix of Hindi and English as spoken in India. "
            "Write it the way a young Indian would explain to a friend: "
            "some sentences in Hindi, some in English, technical terms in English. "
            "Use Devanagari script for Hindi words."
        )
    elif lang_code == "en":
        lang_instruction = "Explain this YouTube video in clear English."
    else:
        lang_instruction = f"Explain this YouTube video fully in {lang_label.split()[-1]} language."

    prompt = f"""{lang_instruction}

Video Details:
- Title: {title}
- Channel: {channel}
- Duration: {duration}
- Views: {views}
- Likes: {likes}
- Tags: {tags}
- Description: {desc}

Please provide:
1. **Video Summary** — What is this video about? (2-3 lines)
2. **Main Topics Covered** — Key points as bullet list
3. **Who Should Watch** — Target audience
4. **Worth Watching?** — Your honest recommendation with reason
5. **Quick Stats Analysis** — Comment on views/likes ratio

Keep it engaging, informative, and helpful."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.7,
            "maxOutputTokens": 1200,
            "topP":            0.9,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }

    # Build candidate model list: fetch live list first, then fall back to hardcoded
    live_models  = list_gemini_models(api_key)
    # Prefer flash/lite models (faster + cheaper), put them first
    prefer_order = ["flash", "lite", "pro"]
    def model_rank(name):
        for i, kw in enumerate(prefer_order):
            if kw in name:
                return i
        return 99
    live_sorted  = sorted(live_models, key=model_rank)
    candidates   = live_sorted + [m for m in GEMINI_MODELS if m not in live_sorted]

    last_error = None
    tried = []
    for model in candidates:
        for base in [GEMINI_BASE_V1, GEMINI_BASE_BETA]:
            url = f"{base}/{model}:generateContent"
            tried.append(f"{base.split('/')[-2]}/{model}")
            try:
                r = requests.post(url, params={"key": api_key},
                                  json=payload, timeout=60)
                if r.status_code in (404, 400):
                    last_error = f"{r.status_code}: {r.json().get('error',{}).get('message','not found')}"
                    continue
                r.raise_for_status()
                data = r.json()
                explanation = data["candidates"][0]["content"]["parts"][0]["text"]
                explanation += f"\n\n─────\n_Explained by: `{model}` (via {base.split('/')[-2]})_"
                break  # inner for
            except (KeyError, IndexError):
                last_error = f"Parse error for '{model}'"
                continue
            except requests.HTTPError as e:
                last_error = http_err_msg(e)
                skip_kw = ("not found","not supported","deprecated","invalid model")
                if any(k in last_error.lower() for k in skip_kw):
                    continue
                raise
        else:
            continue  # tried both bases, move to next model
        break         # inner succeeded, stop outer loop
    else:
        raise RuntimeError(
            f"❌ No working Gemini model found.\n"
            f"Last error: {last_error}\n\n"
            f"Tried {len(tried)} combinations. Make sure:\n"
            f"  1. 'Generative Language API' is ENABLED\n"
            f"     console.cloud.google.com → APIs & Services\n"
            f"  2. Your API key has no HTTP referrer restrictions\n"
            f"  3. Billing is enabled on the project"
        )

    # Translate if non-English & non-Hinglish
    if lang_code not in ("en", "hinglish"):
        explanation = google_translate(api_key, explanation, lang_code)

    return explanation


def google_translate(api_key: str, text: str, target_lang: str) -> str:
    """Translate text using Google Cloud Translation API v2."""
    payload = {
        "q":      text,
        "target": target_lang,
        "format": "text",
        "key":    api_key,
    }
    r = requests.post(TRANSLATE_URL, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    try:
        return data["data"]["translations"][0]["translatedText"]
    except (KeyError, IndexError):
        return text   # fallback: return original if translate fails


def fmt_dur(iso: str) -> str:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return iso
    h, mi, s = (int(x or 0) for x in m.groups())
    return f"{h}:{mi:02}:{s:02}" if h else f"{mi}:{s:02}"


def http_err_msg(e: requests.HTTPError) -> str:
    try:
        d = e.response.json()
        # Gemini error format
        if "error" in d:
            return d["error"].get("message", str(e))
        return str(e)
    except Exception:
        return str(e)


def fetch_image(url: str, size: tuple):
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
#  AI Panel  (right side)
# ═══════════════════════════════════════════════════════════
class AIPanel(ctk.CTkFrame):
    def __init__(self, master, get_key_fn, **kw):
        super().__init__(master, fg_color=AI_PANEL, corner_radius=0, **kw)
        self._get_key   = get_key_fn
        self._video     = None
        self._busy      = False
        self._build()

    def _build(self):
        # ── Header ──
        hdr = ctk.CTkFrame(self, fg_color="#080818", corner_radius=0, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Google Gemini logo area
        logo_f = ctk.CTkFrame(hdr, fg_color="transparent")
        logo_f.pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(logo_f, text="✦", text_color="#EA4335",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkLabel(logo_f, text="✦", text_color="#FBBC04",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkLabel(logo_f, text="✦", text_color="#34A853",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkLabel(logo_f, text=" Gemini AI Explainer", text_color=GEMINI,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        # ── Language dropdown ──
        lang_f = ctk.CTkFrame(self, fg_color="#0A0A18", corner_radius=0, height=42)
        lang_f.pack(fill="x")
        lang_f.pack_propagate(False)

        ctk.CTkLabel(lang_f, text="🌐 Language:", text_color=GREY,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(12, 6), pady=10)

        self.lang_var = tk.StringVar(value="🇮🇳 Hinglish")
        self.lang_menu = ctk.CTkOptionMenu(
            lang_f,
            variable=self.lang_var,
            values=list(LANGUAGES.keys()),
            fg_color="#1A1A3A",
            button_color=ACCENT,
            button_hover_color="#1A6CE8",
            dropdown_fg_color="#1A1A3A",
            dropdown_hover_color="#2A2A5A",
            text_color=WHITE,
            font=ctk.CTkFont(size=12),
            width=170, height=30,
            command=self._on_lang_change)
        self.lang_menu.pack(side="left", padx=4, pady=6)

        self.translate_badge = ctk.CTkLabel(
            lang_f, text="", text_color=GREEN,
            font=ctk.CTkFont(size=10))
        self.translate_badge.pack(side="left", padx=6)

        # ── Video info strip ──
        self.info_frame = ctk.CTkFrame(self, fg_color="#0F0F22",
                                        corner_radius=0, height=78)
        self.info_frame.pack(fill="x")
        self.info_frame.pack_propagate(False)

        self.thumb_lbl = ctk.CTkLabel(self.info_frame, text="🎬",
                                       width=116, height=65,
                                       fg_color="#070712", corner_radius=6,
                                       text_color=LGREY,
                                       font=ctk.CTkFont(size=22))
        self.thumb_lbl.pack(side="left", padx=8, pady=6)

        txt_f = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        txt_f.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        self.title_lbl = ctk.CTkLabel(
            txt_f,
            text="← Click  🤖 Explain  on any video",
            text_color=GREY,
            wraplength=215,
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w", justify="left")
        self.title_lbl.pack(anchor="w", pady=(4, 2))

        self.meta_lbl = ctk.CTkLabel(
            txt_f, text="", text_color=LGREY,
            font=ctk.CTkFont(size=10), anchor="w")
        self.meta_lbl.pack(anchor="w")

        self.stats_lbl = ctk.CTkLabel(
            txt_f, text="", text_color=LGREY,
            font=ctk.CTkFont(size=10), anchor="w")
        self.stats_lbl.pack(anchor="w")

        # ── Explain button ──
        self.explain_btn = ctk.CTkButton(
            self,
            text="✦  Ask Gemini to Explain",
            fg_color=ACCENT,
            hover_color="#1A6CE8",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=42, corner_radius=8,
            state="disabled",
            command=self._explain)
        self.explain_btn.pack(fill="x", padx=12, pady=(8, 4))

        # Progress bar (hidden by default)
        self.progress = ctk.CTkProgressBar(self, mode="indeterminate",
                                            fg_color="#1A1A3A",
                                            progress_color=ACCENT,
                                            height=4, corner_radius=2)
        self.progress.pack(fill="x", padx=12)
        self.progress.set(0)

        # ── Response area ──
        resp_hdr = ctk.CTkFrame(self, fg_color="transparent")
        resp_hdr.pack(fill="x", padx=12, pady=(6, 2))

        ctk.CTkLabel(resp_hdr, text="📄 Explanation:", text_color=GREY,
                     font=ctk.CTkFont(size=11)).pack(side="left")

        self.ai_status = ctk.CTkLabel(resp_hdr, text="", text_color=GEMINI,
                                       font=ctk.CTkFont(size=11, weight="bold"))
        self.ai_status.pack(side="right")

        self.response_box = ctk.CTkTextbox(
            self,
            fg_color="#08080F",
            text_color="#E8E8FF",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            corner_radius=8, wrap="word",
            scrollbar_button_color="#222240",
            scrollbar_button_hover_color="#333360",
            border_width=1,
            border_color="#1A1A3A")
        self.response_box.pack(fill="both", expand=True, padx=10, pady=(2, 6))
        self.response_box.configure(state="disabled")

        # ── Bottom buttons ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        for text, cmd, col in [
            ("📋 Copy",      self._copy,          "#1A2A4A"),
            ("🔄 Re-explain", self._explain,       "#1A2A2A"),
            ("🗑 Clear",      self._clear_text,    "#2A1A1A"),
        ]:
            ctk.CTkButton(btn_row, text=text, height=30,
                          fg_color=col, hover_color="#333360",
                          font=ctk.CTkFont(size=11),
                          command=cmd).pack(side="left", padx=3, expand=True, fill="x")

    # ── Load video into panel ──────────────────────
    def load_video(self, video_info: dict, thumb_url: str = ""):
        self._video = video_info
        title   = video_info.get("title", "—")[:75]
        channel = video_info.get("channel", "—")
        views   = video_info.get("views", "")
        dur     = video_info.get("duration", "")

        self.title_lbl.configure(text=title, text_color=WHITE)
        self.meta_lbl.configure(text=f"📺 {channel}")
        stats_parts = []
        if views:
            try:   stats_parts.append(f"👁 {int(views):,}")
            except Exception: pass
        if dur:
            stats_parts.append(f"⏱ {dur}")
        self.stats_lbl.configure(text="  ".join(stats_parts))
        self.explain_btn.configure(state="normal")
        self._set_status("")

        if thumb_url:
            threading.Thread(target=self._load_thumb,
                             args=(thumb_url,), daemon=True).start()

    def _load_thumb(self, url):
        photo = fetch_image(url, (116, 65))
        if photo:
            self.thumb_lbl.configure(image=photo, text="")
            self.thumb_lbl._img = photo

    def _on_lang_change(self, choice):
        code = LANGUAGES.get(choice, "en")
        if code not in ("en", "hinglish"):
            self.translate_badge.configure(
                text=f"🔤 via Google Translate → {choice.split()[-1]}")
        else:
            self.translate_badge.configure(text="")

    # ── Run explanation ────────────────────────────
    def _explain(self):
        if self._busy or not self._video:
            return
        key = self._get_key()
        if not key:
            self._write(
                "⚠️  Google API Key not set!\n\n"
                "Click  🔑 API Key  in the header.\n\n"
                "Make sure you have enabled:\n"
                "  • Generative Language API (Gemini)\n"
                "  • Cloud Translation API\n"
                "  • YouTube Data API v3\n\n"
                "All from: console.cloud.google.com"
            )
            return

        lang_label = self.lang_var.get()
        lang_code  = LANGUAGES.get(lang_label, "en")

        self._busy = True
        self.explain_btn.configure(state="disabled", text="⏳  Gemini is thinking…")
        self.progress.pack(fill="x", padx=12)
        self.progress.start()
        self._write(
            f"🔄  Calling Gemini AI...\n"
            f"📌  Language: {lang_label}\n"
            f"🔍  Auto-detecting best available model...\n\n"
        )
        self._set_status("⏳ Working…")

        threading.Thread(target=self._worker,
                         args=(key, lang_label, lang_code),
                         daemon=True).start()

    def _worker(self, key, lang_label, lang_code):
        try:
            result = gemini_explain(key, self._video, lang_label, lang_code)
            self.after(0, self._write, result)
            self.after(0, self._set_status, "✅ Done")
        except requests.HTTPError as e:
            msg = http_err_msg(e)
            self.after(0, self._write,
                       f"❌  Google API Error:\n{msg}\n\n"
                       f"Check that 'Generative Language API' is enabled\n"
                       f"at console.cloud.google.com")
            self.after(0, self._set_status, "❌ Error")
        except Exception as e:
            self.after(0, self._write, f"❌  Error: {e}")
            self.after(0, self._set_status, "❌ Error")
        finally:
            self.after(0, self._done)

    def _done(self):
        self._busy = False
        self.progress.stop()
        self.progress.pack_forget()
        self.explain_btn.configure(state="normal",
                                   text="✦  Ask Gemini to Explain")

    def _write(self, text: str):
        self.response_box.configure(state="normal")
        self.response_box.delete("1.0", "end")
        self.response_box.insert("end", text)
        self.response_box.configure(state="disabled")
        self.response_box.see("1.0")

    def _copy(self):
        txt = self.response_box.get("1.0", "end").strip()
        if txt:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self._set_status("📋 Copied!")
            self.after(2000, lambda: self._set_status(""))

    def _clear_text(self):
        self.response_box.configure(state="normal")
        self.response_box.delete("1.0", "end")
        self.response_box.configure(state="disabled")
        self._set_status("")

    def _set_status(self, msg: str):
        self.ai_status.configure(text=msg)


# ═══════════════════════════════════════════════════════════
#  Video Card
# ═══════════════════════════════════════════════════════════
class VideoCard(ctk.CTkFrame):
    def __init__(self, master, snippet, video_id, stats, on_explain, **kw):
        super().__init__(master, fg_color=CARD_BG, corner_radius=12, **kw)
        self.video_id   = video_id
        self.snippet    = snippet
        self.stats      = stats
        self.on_explain = on_explain
        self._thumb_url = ""
        self._build()

    def _build(self):
        s, stats = self.snippet, self.stats
        title     = s.get("title", "—")
        channel   = s.get("channelTitle", "—")
        self._thumb_url = (s.get("thumbnails", {}).get("medium") or
                           s.get("thumbnails", {}).get("default") or {}).get("url", "")
        views = stats.get("viewCount", "")
        dur   = stats.get("duration", "")
        likes = stats.get("likeCount", "")

        # Thumbnail
        self.thumb_lbl = ctk.CTkLabel(
            self, text="🎬", width=THUMB_W, height=THUMB_H,
            fg_color="#111", corner_radius=8,
            text_color=LGREY, font=ctk.CTkFont(size=28))
        self.thumb_lbl.pack(padx=8, pady=(8, 4))
        if self._thumb_url:
            threading.Thread(target=self._load_thumb,
                             args=(self._thumb_url,), daemon=True).start()

        # Title
        ctk.CTkLabel(self, text=title, text_color=WHITE,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     wraplength=210, justify="left", anchor="w"
                     ).pack(padx=10, fill="x")

        # Channel
        ctk.CTkLabel(self, text=f"📺 {channel}", text_color=GREY,
                     font=ctk.CTkFont(size=10), anchor="w"
                     ).pack(padx=10, fill="x", pady=(1, 0))

        # Stats row
        parts = []
        if views:
            try:   parts.append(f"👁 {int(views):,}")
            except Exception: pass
        if likes:
            try:   parts.append(f"👍 {int(likes):,}")
            except Exception: pass
        if dur:
            parts.append(f"⏱ {fmt_dur(dur)}")
        if parts:
            ctk.CTkLabel(self, text="  ".join(parts), text_color=LGREY,
                         font=ctk.CTkFont(size=10), anchor="w"
                         ).pack(padx=10, fill="x", pady=(2, 5))

        # Buttons
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(padx=10, pady=(0, 10), fill="x")

        ctk.CTkButton(btn_f, text="▶ Watch",
                      fg_color=RED, hover_color="#BB0000",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      height=32, corner_radius=6,
                      command=self._open
                      ).pack(side="left", expand=True, fill="x", padx=(0, 3))

        ctk.CTkButton(btn_f, text="✦ Explain",
                      fg_color=ACCENT, hover_color="#1A6CE8",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      height=32, corner_radius=6,
                      command=self._explain
                      ).pack(side="left", expand=True, fill="x")

    def _load_thumb(self, url):
        photo = fetch_image(url, (THUMB_W, THUMB_H))
        if photo:
            self.thumb_lbl.configure(image=photo, text="")
            self.thumb_lbl._img = photo

    def _open(self):
        webbrowser.open(f"https://www.youtube.com/watch?v={self.video_id}")

    def _explain(self):
        s = self.snippet
        info = {
            "title":       s.get("title", ""),
            "channel":     s.get("channelTitle", ""),
            "description": s.get("description", ""),
            "views":       self.stats.get("viewCount", ""),
            "likes":       self.stats.get("likeCount", ""),
            "duration":    fmt_dur(self.stats.get("duration", "")),
            "tags":        self.stats.get("tags", []),
            "video_id":    self.video_id,
        }
        self.on_explain(info, self._thumb_url)


# ═══════════════════════════════════════════════════════════
#  Channel Card
# ═══════════════════════════════════════════════════════════
class ChannelCard(ctk.CTkFrame):
    def __init__(self, master, snippet, channel_id, stats, **kw):
        super().__init__(master, fg_color=CARD_BG, corner_radius=12, **kw)
        self.channel_id = channel_id
        self._build(snippet, stats)

    def _build(self, s, stats):
        name  = s.get("title", "—")
        desc  = s.get("description", "")[:110]
        thumb = (s.get("thumbnails", {}).get("medium") or
                 s.get("thumbnails", {}).get("default") or {}).get("url", "")
        subs  = stats.get("subscriberCount", "")
        vids  = stats.get("videoCount", "")

        self.avatar = ctk.CTkLabel(self, text="📺", width=76, height=76,
                                    fg_color="#111", corner_radius=38,
                                    text_color=LGREY,
                                    font=ctk.CTkFont(size=28))
        self.avatar.pack(pady=(12, 5))
        if thumb:
            threading.Thread(target=self._load_avatar,
                             args=(thumb,), daemon=True).start()

        ctk.CTkLabel(self, text=name, text_color=WHITE,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(padx=8)

        meta = []
        if subs:
            try:   meta.append(f"👥 {int(subs):,}")
            except Exception: pass
        if vids:
            try:   meta.append(f"🎬 {int(vids):,}")
            except Exception: pass
        if meta:
            ctk.CTkLabel(self, text="  ".join(meta), text_color=GREY,
                         font=ctk.CTkFont(size=11)).pack(pady=2)

        if desc:
            ctk.CTkLabel(self, text=desc, text_color=GREY,
                         font=ctk.CTkFont(size=10),
                         wraplength=185, justify="center"
                         ).pack(padx=8, pady=3)

        ctk.CTkButton(self, text="Open Channel", fg_color=RED,
                      hover_color="#BB0000", height=30, corner_radius=6,
                      command=self._open
                      ).pack(padx=10, pady=(4, 12), fill="x")

    def _load_avatar(self, url):
        photo = fetch_image(url, (76, 76))
        if photo:
            self.avatar.configure(image=photo, text="")
            self.avatar._img = photo

    def _open(self):
        webbrowser.open(f"https://www.youtube.com/channel/{self.channel_id}")


# ═══════════════════════════════════════════════════════════
#  API Key Dialog  (single Google key)
# ═══════════════════════════════════════════════════════════
class ApiKeyDialog(ctk.CTkToplevel):
    def __init__(self, master, current_key: str, callback):
        super().__init__(master)
        self.title("Google API Key Setup")
        self.geometry("560x400")
        self.resizable(False, False)
        self.grab_set()
        self.callback = callback
        self._build(current_key)

    def _build(self, current_key):
        # Google color header
        hdr = ctk.CTkFrame(self, fg_color="#1A1A2E", corner_radius=0, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        logo_f = ctk.CTkFrame(hdr, fg_color="transparent")
        logo_f.pack(expand=True)
        for ch, col in [("G", "#EA4335"), ("o", "#FBBC04"), ("o", "#34A853"),
                         ("g", "#4285F4"), ("l", "#EA4335"), ("e", "#34A853")]:
            ctk.CTkLabel(logo_f, text=ch, text_color=col,
                         font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")
        ctk.CTkLabel(logo_f, text=" Cloud Console", text_color=WHITE,
                     font=ctk.CTkFont(size=18)).pack(side="left")

        ctk.CTkLabel(self,
                     text="One API Key enables all three Google APIs:",
                     text_color=WHITE,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(16, 4))

        # API list
        apis_f = ctk.CTkFrame(self, fg_color="#111130", corner_radius=8)
        apis_f.pack(padx=24, pady=4, fill="x")

        apis = [
            ("🎬", "#FF0000", "YouTube Data API v3",       "Video search & channel info"),
            ("✦", "#4285F4", "Generative Language API",    "Gemini AI explanations"),
            ("🌐", "#34A853", "Cloud Translation API",     "Translate to 10+ languages"),
        ]
        for icon, color, name, desc in apis:
            row = ctk.CTkFrame(apis_f, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=5)
            ctk.CTkLabel(row, text=icon, text_color=color,
                         font=ctk.CTkFont(size=14), width=24).pack(side="left")
            ctk.CTkLabel(row, text=name, text_color=WHITE,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         width=220, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(row, text=desc, text_color=GREY,
                         font=ctk.CTkFont(size=11)).pack(side="left")

        ctk.CTkLabel(self,
                     text="→  console.cloud.google.com  →  Enable APIs  →  Credentials  →  Create API Key",
                     text_color=LGREY, font=ctk.CTkFont(size=10)).pack(pady=(8, 4))

        self.key_entry = ctk.CTkEntry(self, width=510, height=40,
                                       placeholder_text="Paste your Google API Key here  (AIzaSy...)",
                                       font=ctk.CTkFont(size=13))
        self.key_entry.pack(padx=24, pady=6)
        if current_key:
            self.key_entry.insert(0, current_key)

        ctk.CTkButton(self, text="✅  Save & Start", fg_color=ACCENT,
                      hover_color="#1A6CE8", width=220, height=40,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(pady=10)

    def _save(self):
        key = self.key_entry.get().strip()
        if not key:
            messagebox.showwarning("Missing Key",
                                   "Please enter your Google API key.", parent=self)
            return
        self.callback(key)
        self.destroy()


# ═══════════════════════════════════════════════════════════
#  Main Application
# ═══════════════════════════════════════════════════════════
class YouTubeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PyTube Player  +  Google Gemini AI")
        self.geometry("1440x800")
        self.minsize(920, 600)
        self.configure(fg_color=DARK_BG)

        self._api_key     = GOOGLE_API_KEY.strip()
        self._tab         = "videos"
        self._debounce_id = None

        self._build_ui()

        if not self._api_key:
            self.after(400, self._open_key_dialog)

    # ── Build UI ──────────────────────────────────
    def _build_ui(self):
        # ── Header ──
        hdr = ctk.CTkFrame(self, fg_color="#060606", height=66, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Logo
        logo_f = ctk.CTkFrame(hdr, fg_color="transparent")
        logo_f.pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(logo_f, text="▶", text_color=RED,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        ctk.CTkLabel(logo_f, text=" PyTube", text_color=WHITE,
                     font=ctk.CTkFont(family="Georgia", size=20, weight="bold")
                     ).pack(side="left")
        ctk.CTkLabel(logo_f, text="  +  ", text_color=LGREY,
                     font=ctk.CTkFont(size=14)).pack(side="left")
        for ch, col in [("G", "#EA4335"), ("e", "#FBBC04"), ("m", "#34A853"),
                         ("i", "#4285F4"), ("n", "#EA4335"), ("i", "#34A853")]:
            ctk.CTkLabel(logo_f, text=ch, text_color=col,
                         font=ctk.CTkFont(size=17, weight="bold")).pack(side="left")

        # Search bar
        sb = ctk.CTkFrame(hdr, fg_color="#1A1A1A", corner_radius=26)
        sb.pack(side="left", padx=12, pady=12, fill="x", expand=True)

        self.q_var = tk.StringVar()
        self.q_var.trace_add("write", self._on_type)

        self.entry = ctk.CTkEntry(
            sb, textvariable=self.q_var,
            placeholder_text="Search YouTube…",
            border_width=0, fg_color="transparent",
            font=ctk.CTkFont(size=14), text_color=WHITE, height=42)
        self.entry.pack(side="left", fill="x", expand=True, padx=16)
        self.entry.bind("<Return>", lambda e: self._do_search())

        ctk.CTkButton(sb, text="🔍", width=48, height=42,
                      fg_color="transparent", hover_color=HOVER_BG,
                      font=ctk.CTkFont(size=17),
                      command=self._do_search).pack(side="right", padx=4)

        ctk.CTkButton(hdr, text="🔑 API Key", width=106, height=38,
                      fg_color="#1A1A3A", hover_color="#2A2A5A",
                      font=ctk.CTkFont(size=12),
                      command=self._open_key_dialog
                      ).pack(side="right", padx=12)

        # ── Tab bar ──
        tbar = ctk.CTkFrame(self, fg_color="#0A0A0A", height=46, corner_radius=0)
        tbar.pack(fill="x")
        tbar.pack_propagate(False)

        self.btn_vid = ctk.CTkButton(
            tbar, text="🎬  Videos", width=130, height=42,
            fg_color=RED, hover_color="#BB0000", corner_radius=0,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self._switch("videos"))
        self.btn_vid.pack(side="left", padx=(18, 4))

        self.btn_ch = ctk.CTkButton(
            tbar, text="📺  Channels", width=130, height=42,
            fg_color="transparent", hover_color=HOVER_BG, corner_radius=0,
            font=ctk.CTkFont(size=13),
            command=lambda: self._switch("channels"))
        self.btn_ch.pack(side="left")

        self.status_lbl = ctk.CTkLabel(tbar, text="", text_color=GREY,
                                        font=ctk.CTkFont(size=12))
        self.status_lbl.pack(side="right", padx=18)

        # ── Body ──
        body = ctk.CTkFrame(self, fg_color=DARK_BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        # Results (left, scrollable)
        self.results = ctk.CTkScrollableFrame(
            body, fg_color=DARK_BG,
            scrollbar_button_color="#222",
            scrollbar_button_hover_color="#444")
        self.results.pack(side="left", fill="both", expand=True,
                          padx=(8, 4), pady=8)

        # AI Panel (right, fixed width)
        self.ai_panel = AIPanel(body, get_key_fn=lambda: self._api_key, width=370)
        self.ai_panel.pack(side="right", fill="y")
        self.ai_panel.pack_propagate(False)

        self._welcome()

    # ── Welcome ───────────────────────────────────
    def _welcome(self):
        self._clear()
        f = ctk.CTkFrame(self.results, fg_color="transparent")
        f.pack(expand=True, pady=70)

        ctk.CTkLabel(f, text="▶", text_color=RED,
                     font=ctk.CTkFont(size=70)).pack()
        ctk.CTkLabel(f, text="PyTube Player", text_color=WHITE,
                     font=ctk.CTkFont(family="Georgia", size=28, weight="bold")
                     ).pack(pady=6)

        # Google colored subtitle
        sub_f = ctk.CTkFrame(f, fg_color="transparent")
        sub_f.pack()
        ctk.CTkLabel(sub_f, text="Powered by ", text_color=GREY,
                     font=ctk.CTkFont(size=13)).pack(side="left")
        for ch, col in [("G","#EA4335"),("o","#FBBC04"),("o","#34A853"),
                         ("g","#4285F4"),("l","#EA4335"),("e","#34A853")]:
            ctk.CTkLabel(sub_f, text=ch, text_color=col,
                         font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkLabel(sub_f, text=" APIs", text_color=GREY,
                     font=ctk.CTkFont(size=13)).pack(side="left")

        ctk.CTkLabel(f, text="\nSearch karo  →  Video dhoondo  →  ✦ Explain daba  →  AI se samjho! 🚀",
                     text_color=GREY, font=ctk.CTkFont(size=12)).pack()

        # Features
        feats = [
            ("🎬", "YouTube Search",      "Videos & Channels"),
            ("✦", "Gemini AI",            "Smart explanations"),
            ("🌐", "10+ Languages",       "Hindi, English, Hinglish & more"),
            ("🔑", "One Key",             "All APIs from Google Console"),
        ]
        feat_f = ctk.CTkFrame(f, fg_color="#111118", corner_radius=10)
        feat_f.pack(pady=16, padx=20, fill="x")
        for row_i in range(0, len(feats), 2):
            row_f = ctk.CTkFrame(feat_f, fg_color="transparent")
            row_f.pack(fill="x")
            for icon, title, sub in feats[row_i:row_i+2]:
                item = ctk.CTkFrame(row_f, fg_color="transparent")
                item.pack(side="left", expand=True, padx=12, pady=8)
                ctk.CTkLabel(item, text=f"{icon} {title}", text_color=WHITE,
                             font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
                ctk.CTkLabel(item, text=sub, text_color=LGREY,
                             font=ctk.CTkFont(size=11)).pack(anchor="w")

    # ── Tab switch ────────────────────────────────
    def _switch(self, tab: str):
        self._tab = tab
        self.btn_vid.configure(fg_color=RED if tab == "videos" else "transparent")
        self.btn_ch.configure(fg_color=RED if tab == "channels" else "transparent")
        if self.q_var.get().strip():
            self._do_search()

    # ── Debounce ──────────────────────────────────
    def _on_type(self, *_):
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(700, self._do_search)

    # ── Search ────────────────────────────────────
    def _do_search(self):
        q = self.q_var.get().strip()
        if not q:
            self._welcome()
            return
        if not self._api_key:
            self._open_key_dialog()
            return
        self._clear()
        self._set_status("🔍 Searching…")
        if self._tab == "videos":
            threading.Thread(target=self._fetch_videos,
                             args=(q,), daemon=True).start()
        else:
            threading.Thread(target=self._fetch_channels,
                             args=(q,), daemon=True).start()

    # ── Fetch Videos ─────────────────────────────
    def _fetch_videos(self, q: str):
        try:
            data  = yt_get(YT_SEARCH_URL,
                           {"part": "snippet", "q": q,
                            "type": "video", "maxResults": 20}, self._api_key)
            items = data.get("items", [])
            if not items:
                self.after(0, self._set_status, "No results found.")
                return

            ids = ",".join(i["id"]["videoId"] for i in items
                           if i.get("id", {}).get("videoId"))
            vdata = yt_get(YT_VIDEOS_URL,
                           {"part": "statistics,contentDetails,snippet",
                            "id": ids}, self._api_key)
            stats_map = {}
            for v in vdata.get("items", []):
                stats_map[v["id"]] = {
                    **v.get("statistics", {}),
                    "duration": v["contentDetails"].get("duration", ""),
                    "tags":     v.get("snippet", {}).get("tags", []),
                }
            self.after(0, self._render_videos, items, stats_map)
        except requests.HTTPError as e:
            self.after(0, self._set_status, f"❌ API Error: {http_err_msg(e)}")
        except Exception as e:
            self.after(0, self._set_status, f"❌ Error: {e}")

    # ── Fetch Channels ────────────────────────────
    def _fetch_channels(self, q: str):
        try:
            data  = yt_get(YT_SEARCH_URL,
                           {"part": "snippet", "q": q,
                            "type": "channel", "maxResults": 16}, self._api_key)
            items = data.get("items", [])
            if not items:
                self.after(0, self._set_status, "No channels found.")
                return

            ids = ",".join(i["id"]["channelId"] for i in items
                           if i.get("id", {}).get("channelId"))
            cdata = yt_get(YT_CHANNEL_URL,
                           {"part": "statistics", "id": ids}, self._api_key)
            stats_map = {v["id"]: v.get("statistics", {})
                         for v in cdata.get("items", [])}
            self.after(0, self._render_channels, items, stats_map)
        except requests.HTTPError as e:
            self.after(0, self._set_status, f"❌ API Error: {http_err_msg(e)}")
        except Exception as e:
            self.after(0, self._set_status, f"❌ Error: {e}")

    # ── Render Videos ─────────────────────────────
    def _render_videos(self, items, stats_map):
        self._clear()
        self._set_status(f"🎬 {len(items)} videos found")
        grid = ctk.CTkFrame(self.results, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        cols = max(1, (self.results.winfo_width() - 20) // (THUMB_W + 38))
        for i, item in enumerate(items):
            vid_id  = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {})
            stats   = stats_map.get(vid_id, {})
            card = VideoCard(grid, snippet, vid_id, stats,
                             on_explain=self._on_explain,
                             width=THUMB_W + 22)
            card.grid(row=i // cols, column=i % cols,
                      padx=10, pady=10, sticky="n")

    # ── Render Channels ───────────────────────────
    def _render_channels(self, items, stats_map):
        self._clear()
        self._set_status(f"📺 {len(items)} channels found")
        grid = ctk.CTkFrame(self.results, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        cols = max(1, (self.results.winfo_width() - 20) // 220)
        for i, item in enumerate(items):
            ch_id   = item.get("id", {}).get("channelId", "")
            snippet = item.get("snippet", {})
            stats   = stats_map.get(ch_id, {})
            card = ChannelCard(grid, snippet, ch_id, stats, width=200)
            card.grid(row=i // cols, column=i % cols,
                      padx=10, pady=10, sticky="n")

    # ── Explain callback ──────────────────────────
    def _on_explain(self, video_info: dict, thumb_url: str):
        self.ai_panel.load_video(video_info, thumb_url)

    # ── Key dialog ────────────────────────────────
    def _open_key_dialog(self):
        def save(key):
            self._api_key = key
            self._set_status("✅ API Key saved — ready!")
        ApiKeyDialog(self, self._api_key, save)

    # ── Utils ─────────────────────────────────────
    def _clear(self):
        for w in self.results.winfo_children():
            w.destroy()

    def _set_status(self, msg: str):
        self.status_lbl.configure(text=msg)


# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = YouTubeApp()
    app.mainloop()
