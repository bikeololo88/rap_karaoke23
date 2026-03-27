#!/usr/bin/env python3
"""
Rap Karaoke Converter — Ultimate Edition
========================================
Слияние лучших фичей: LRCLIB парсинг, Phonetic Slang, UVR сепарация,
кэширование по MD5, поддержка видео-фонов и умный рендер эдлибов.
"""

import sys, os, re, shutil, argparse, subprocess, tempfile, json, hashlib
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import jellyfish


# ══════════════════════════════════════════════════════════════════════════════
#  ГЛОБАЛЬНЫЕ НАСТРОЙКИ И ПУТИ
# ══════════════════════════════════════════════════════════════════════════════
CACHE_DIR = Path.home() / ".cache" / "rap_karaoke"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT  = 1280, 720
FPS            = 24

BG_TOP         = (8,   8,  18)
BG_BOT         = (18,  8,  28)
SCANLINE_ALPHA = 18

COLOR_PAST     = (80,  80, 100)
COLOR_CURRENT  = (255, 220,  40)
COLOR_FUTURE   = (200, 200, 230)

FONT_SIZE_MAIN = 52
FONT_SIZE_SUB  = 38
LINE_GAP       = 20
CONTEXT_LINES  = 1
WORDS_PER_LINE = 6

PROG_H      = 6
PROG_COLOR  = (255, 220, 40)
PROG_BG     = ( 40,  40, 60)

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

# ══════════════════════════════════════════════════════════════════════════════
#  ДЕТЕКТОР GPU
# ══════════════════════════════════════════════════════════════════════════════
class GPU:
    device: str; torch_device: str; compute_type: str; backend: str; name: str
    def __init__(self): self._detect()
    def _detect(self):
        try:
            import torch
            if torch.cuda.is_available():
                idx = torch.cuda.current_device()
                name = torch.cuda.get_device_name(idx)
                vram = torch.cuda.get_device_properties(idx).total_memory // (1024**3)
                self.backend, self.device, self.torch_device = "nvidia", "cuda", f"cuda:{idx}"
                self.compute_type = "float16" if torch.cuda.get_device_capability(idx)[0] >= 7 else "int8_float16"
                self.name = f"NVIDIA {name} ({vram} GB VRAM)"
                return
            if self._rocm_available():
                self.backend, self.device, self.torch_device = "amd", "cuda", "cuda"
                self.compute_type, self.name = "float16", self._rocm_name()
                return
        except ImportError: pass
        import platform, multiprocessing
        self.backend, self.device, self.torch_device = "cpu", "cpu", "cpu"
        self.compute_type = "int8"
        self.name = f"CPU ({platform.processor() or 'unknown'}, {multiprocessing.cpu_count()} ядер)"

    @staticmethod
    def _rocm_available():
        if Path("/sys/class/kfd/kfd/topology/nodes").exists(): return True
        if shutil.which("rocm-smi"):
            try: return "GPU" in subprocess.run(["rocm-smi", "--showproductname"], capture_output=True, text=True, timeout=5).stdout.upper()
            except: pass
        return False

    @staticmethod
    def _rocm_name():
        if shutil.which("rocm-smi"):
            try:
                for line in subprocess.run(["rocm-smi", "--showproductname"], capture_output=True, text=True).stdout.splitlines():
                    if "GPU" in line.upper() or "Radeon" in line: return "AMD " + line.strip().split(":")[-1].strip()
            except: pass
        return "AMD Radeon (ROCm)"

    def info(self) -> str:
        return f"{'🟢' if self.backend=='nvidia' else '🔴' if self.backend=='amd' else '⚪'} {self.name} [device={self.torch_device}, compute={self.compute_type}]"

_GPU: Optional[GPU] = None
def gpu() -> GPU:
    global _GPU
    if _GPU is None: _GPU = GPU()
    return _GPU

def get_file_hash(filepath: Path) -> str:
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192): h.update(chunk)
    return h.hexdigest()

# ══════════════════════════════════════════════════════════════════════════════
#  СЛОВАРЬ РЭП-СЛЕНГА
# ══════════════════════════════════════════════════════════════════════════════
SLANG: dict[str, str] = {
    "штаконы": "штаконы", "штакон": "штакон", "флоу": "флоу", "дроп": "дроп", 
    "трэп": "трэп", "треп": "трэп", "хайп": "хайп", "хейп": "хайп",
    "свэг": "свэг", "свег": "свэг", "щвег": "свэг", "вайб": "вайб", "вэйб": "вайб",
    "флекс": "флекс", "флексить": "флексить", "дрип": "дрип", "жиза": "жиза",
    "зашквар": "зашквар", "зашкварный": "зашкварный", "кек": "кек", 
    "мани": "мани", "мэни": "мани", "скилл": "скилл", "скил": "скилл",
    "лэвел": "лэвел", "левел": "лэвел", "гангста": "гангста", "бро": "бро",
    "чилить": "чилить", "чилл": "чилл", "коллаб": "коллаб", "колаб": "коллаб",
    "стэк": "стэк", "стак": "стэк", "кэш": "кэш", "кеш": "кэш", "лавэ": "лавэ", 
    "лаве": "лавэ", "факап": "факап", "трэк": "трэк", "трек": "трэк", "хук": "хук",
    "дисс": "дисс", "фристайл": "фристайл", "микстейп": "микстейп", "лейбл": "лейбл",
    "релиз": "релиз", "шмот": "шмот", "шмотки": "шмотки", "сникеры": "сникеры",
    "худи": "худи", "чейн": "чейн", "гуччи": "гуччи", "гучи": "гуччи",
    "версаче": "версаче", "версачи": "версаче", "прада": "прада", "ламба": "ламба",
    "мерс": "мерс", "мэрс": "мерс", "крипта": "крипта", "биток": "биток",
    "хастл": "хастл", "хастлить": "хастлить", "скам": "скам", "нфт": "нфт",
    "ботнет": "ботнет", "слат": "слат", "слатт": "слат", "slatt": "слат",
    "опп": "опп", "оп": "опп", "оппы": "оппы", "опы": "оппы", "кап": "кап",
    "лин": "лин", "лим": "лин", "сироп": "сироп", "гэнг": "гэнг", "генг": "гэнг",
    "ганг": "гэнг", "блок": "блок", "шутер": "шутер", "шутор": "шутер", "айс": "айс",
    "ввс": "ВВС", "vvs": "ВВС", "куш": "куш", "сканк": "сканк", "сканг": "сканк",
    "перк": "перк", "перки": "перки", "броук": "броук", "брок": "броук",
    "кэп": "кэп", "кеп": "кэп", "cap": "кэп", "ноукэп": "ноукэп", "no cap": "ноукэп",
    "пуллап": "пулл ап", "пулап": "пулл ап", "pull up": "пулл ап", "глок": "глок",
    "рнб": "РНБ", "rnb": "РНБ", "тишка": "тишка", "зая": "зая", "скрр": "скрр",
    "скр": "скрр", "скррр": "скрр", "сквад": "сквад", "скват": "сквад",
    "бэнкролл": "бэнкролл", "бенкролл": "бэнкролл", "бенкрол": "бэнкролл",
    "стафф": "стафф", "стаф": "стафф", "биф": "биф", "тру": "тру", "майк": "майк",

    # ── Platina / Mumble Trap Additions ──
    "гуап": "гуап", "гуапо": "гуап",
    "рэки": "рэки", "рэкс": "рэки",
    "чоппа": "чоппа", "чопа": "чоппа",
    "шоти": "шоти",
    "бэй": "бэй",
    "доуп": "доуп",
    "гэс": "гэс", "газ": "гэс",
    "дрэко": "дрэко", "дрейко": "дрэко",
    "щищ": "щищ", "шиш": "щищ",
    "эсщкерит": "эсщкерит", "эщкере": "эсщкерит",
}

def apply_slang(words: list[dict]) -> list[dict]:
    out = []
    for w in words:
        punct_end = ""; clean = w["word"]
        while clean and clean[-1] in ".,!?;:«»\"'":
            punct_end = clean[-1] + punct_end; clean = clean[:-1]
        low = clean.lower()
        fixed = SLANG.get(low, clean)
        if clean and clean[0].isupper(): fixed = fixed[0].upper() + fixed[1:]
        out.append({**w, "word": fixed + punct_end})
    return out

def phonetic_slang(words: list[dict]) -> list[dict]:
    try: import jellyfish
    except ImportError: return words
    def cyr_lat(s): return s.translate(str.maketrans("абвгдеёжзийклмнопрстуфхцчшщьъыэюя", "abvgdeyeziyklmnoprstufhtchshshiyeya"))
    targets = [(v, jellyfish.metaphone(cyr_lat(v))) for v in set(SLANG.values())]
    out = []
    for w in words:
        low = w["word"].lower().strip(".,!?;:«»")
        if low in SLANG:
            out.append({**w, "word": SLANG[low]}); continue
        meta = jellyfish.metaphone(cyr_lat(low))
        match = next((canon for canon, m in targets if m and meta and meta == m), None)
        out.append({**w, "word": match if match else w["word"]})
    return out

# ══════════════════════════════════════════════════════════════════════════════
#  ШАГ 1 — Audio Separator (UVR Models)
# ══════════════════════════════════════════════════════════════════════════════
def separate_stems(input_path: Path, file_hash: str) -> tuple[Path, Path]:
    v_cache = CACHE_DIR / f"{file_hash}_vocals.wav"
    i_cache = CACHE_DIR / f"{file_hash}_instrumental.wav"
    
    if v_cache.exists() and i_cache.exists():
        print("⚡ Найдены закэшированные стемы!")
        return v_cache, i_cache

    print("🎛  UVR: выделяем вокал (сохраняя бэки в минусе)…")
    from audio_separator.separator import Separator
    model_name = "UVR-MDX-NET-Inst_HQ_3.onnx" 
    sep = Separator(output_dir=str(CACHE_DIR), model_file_dir=str(CACHE_DIR / "models"))
    sep.load_model(model_filename=model_name)
    
    out_files = sep.separate(str(input_path))
    
    # Умная раскидовка: ищем по имени файла, сгенерированного либой
    for file in out_files:
        if "Vocals" in file or "vocals" in file.lower():
            shutil.move(CACHE_DIR / file, v_cache)
        else:
            # Если не вокал, значит Instrumental
            shutil.move(CACHE_DIR / file, i_cache)
            
    print(f"   ✓ вокал: {v_cache.name}\n   ✓ минус: {i_cache.name}")
    return v_cache, i_cache

# ══════════════════════════════════════════════════════════════════════════════
#  ШАГ 2 — Поиск текста
# ══════════════════════════════════════════════════════════════════════════════
def _req(url, **kw):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, **kw)
        r.raise_for_status(); return r
    except Exception as e:
        print(f"     ✗ {url[:55]}: {e}"); return None

def _clean(raw: str) -> str:
    # Удаляем только структурные теги вида [Куплет 1], но оставляем (скрр) и [слатт] внутри строк
    lines = [l.strip() for l in raw.splitlines()]
    return "\n".join(re.sub(r'\s+', ' ', l) for l in lines if l and not re.match(r"^\[.*\]$", l))

def _parse_lrc(lrc: str) -> list[dict]:
    enhanced_re = re.compile(r"\[(\d+):(\d+\.\d+)\]((?:<\d+:\d+\.\d+>[^<\[]+)+)")
    standard_re = re.compile(r"\[(\d+):(\d+\.\d+)\]\s*(.*)")
    word_ts_re  = re.compile(r"<(\d+):(\d+\.\d+)>([^<\[]+)")
    words: list[dict] = []
    for line in lrc.splitlines():
        line = line.strip()
        if not line: continue
        em = enhanced_re.match(line)
        if em:
            raw_words = word_ts_re.findall(em.group(3))
            for i, (mm, ss, text) in enumerate(raw_words):
                if not text.strip(): continue
                start = int(mm) * 60 + float(ss)
                end = int(raw_words[i+1][0])*60 + float(raw_words[i+1][1]) if i+1 < len(raw_words) else start + 0.4
                words.append({"word": text.strip(), "start": start, "end": end})
            continue
        sm = standard_re.match(line)
        if sm:
            mm, ss, text = sm.group(1), sm.group(2), sm.group(3).strip()
            if not text or re.match(r"^\[.*\]$", text): continue
            start = int(mm) * 60 + float(ss)
            line_words = text.split()
            dur = 0.35
            for wi, w in enumerate(line_words):
                ws = start + wi * dur
                words.append({"word": w, "start": ws, "end": ws + dur})
    for i in range(len(words) - 1):
        if words[i]["end"] > words[i + 1]["start"]: words[i]["end"] = words[i + 1]["start"]
    return words

def _lrclib(artist, title):
    r = _req("https://lrclib.net/api/search", params={"track_name": title, "artist_name": artist})
    if not r or not r.json(): return None

    results = r.json()
    best_hit = None
    best_score = -1

    # Find the best match based on string similarity, prioritizing synced lyrics
    for hit in results:
        hit_artist = hit.get('artistName', '')
        hit_title = hit.get('trackName', '')
        if not hit_artist and not hit_title: continue

        # Score using Jaro-Winkler similarity
        artist_score = jellyfish.jaro_winkler_similarity(artist.lower(), hit_artist.lower()) if artist else 0.5
        title_score = jellyfish.jaro_winkler_similarity(title.lower(), hit_title.lower())

        # Give more weight to synced lyrics
        synced_bonus = 0.2 if hit.get('syncedLyrics') else 0
        
        score = (artist_score * 0.4) + (title_score * 0.6) + synced_bonus
        
        if score > best_score:
            best_score = score
            best_hit = hit

    # If we found a decent match (threshold can be tuned)
    if best_hit and best_score > 0.75:
        synced = best_hit.get("syncedLyrics")
        plain = (best_hit.get("plainLyrics") or "").strip()
        if synced: return (_parse_lrc(synced), plain)
        if plain: return ([], plain)
            
    return None

def _genius(artist, title):
    r = _req("https://genius.com/api/search/multi", params={"q": f"{artist} {title}"})
    if not r: return None
    try: path = r.json()["response"]["sections"][0]["hits"][0]["result"]["path"]
    except: return None
    page = _req("https://genius.com" + path)
    if not page: return None
    cs = BeautifulSoup(page.text, "html.parser").find_all("div", attrs={"data-lyrics-container": "true"})
    return _clean("\n".join(c.get_text("\n") for c in cs)) if cs else None

def _azlyrics(artist, title):
    r = _req("https://search.azlyrics.com/search.php", params={"q": f"{artist} {title}"})
    if not r: return None
    soup = BeautifulSoup(r.text, "html.parser")
    link = soup.select_one("td.text-left a")
    if not link or not link.get("href", "").startswith("http"): return None
    
    page = _req(link["href"])
    if not page: return None
    
    page_soup = BeautifulSoup(page.text, "html.parser")
    # Lyrics are in a div after a specific comment
    comment_anchor = page_soup.find(string=lambda text: "Usage of azlyrics.com content" in str(text))
    if not comment_anchor: return None
    
    lyrics_div = comment_anchor.find_next('div')
    return _clean(lyrics_div.get_text(separator='\n')) if lyrics_div else None

def _text_lyrics(artist, title):
    r = _req("https://text-lyrics.ru/search.php", params={"q": f"{artist} {title}"})
    if not r: return None
    soup = BeautifulSoup(r.text, "html.parser")
    link = soup.select_one("td.search_result_title a")
    if not link: return None
    page = _req("https://text-lyrics.ru" + link["href"])
    if not page: return None
    lyrics_div = BeautifulSoup(page.text, "html.parser").select_one("div#showtext")
    return _clean(lyrics_div.get_text("\n")) if lyrics_div else None

def _lyricstranslate(artist, title):
    r = _req("https://lyricstranslate.com/en/search", params={"query": f"{artist} {title}"})
    if not r: return None
    soup = BeautifulSoup(r.text, "html.parser")
    link = soup.select_one("div.ltsearch-results-line-title a")
    if not link: return None
    page = _req("https://lyricstranslate.com" + link["href"])
    if not page: return None
    page_soup = BeautifulSoup(page.text, "html.parser")
    lyrics_div = page_soup.find("div", id=re.compile(r"^lyrics-"))
    return _clean(lyrics_div.get_text("\n")) if lyrics_div else None

def _tekstovoi(artist, title):
    r = _req("https://tekstovoi.ru/search", params={"q": f"{artist} {title}"})
    if not r: return None
    link = BeautifulSoup(r.text, "html.parser").select_one("a.song-link")
    if not link: return None
    page = _req("https://tekstovoi.ru" + link["href"])
    if not page: return None
    b = BeautifulSoup(page.text, "html.parser").select_one("div.song-text")
    return _clean(b.get_text("\n")) if b else None

def find_lyrics(artist: str, title: str):
    print(f"🔍 Ищем текст: «{artist} — {title}»")
    print("   → LRCLIB…", end=" ", flush=True)
    lrc_result = _lrclib(artist, title)
    if lrc_result:
        words, plain = lrc_result
        if words: print(f"✓ synced LRC ({len(words)} слов)"); return words, plain
        if plain: print(f"✓ plain text ({len(plain)} симв.)"); return None, plain
    else: print("нет")

    scrapers = [
        ("Genius",          lambda: _genius(artist, title)),
        ("AZLyrics",        lambda: _azlyrics(artist, title)),
        ("text-lyrics.ru",  lambda: _text_lyrics(artist, title)),
        ("tekstovoi.ru",    lambda: _tekstovoi(artist, title)),
        ("lyricstranslate", lambda: _lyricstranslate(artist, title)),
    ]
    for name, fn in scrapers:
        print(f"   → {name}…", end=" ", flush=True)
        res = fn()
        if res and len(res) > 50: print(f"✓ ({len(res)} симв.)"); return None, res
        print("нет")
    return None, None

# ══════════════════════════════════════════════════════════════════════════════
#  ШАГ 3 — Whisper STT / WhisperX (С КЭШЕМ)
# ══════════════════════════════════════════════════════════════════════════════
def get_timings(vocals: Path, file_hash: str, pre_timed: Optional[list[dict]], plain_lyrics: Optional[str], model_name: str, lang: str, no_align: bool) -> list[dict]:
    t_cache = CACHE_DIR / f"{file_hash}_timings.json"
    if t_cache.exists():
        print("⚡ Найдены закэшированные тайминги!")
        with open(t_cache, "r", encoding="utf-8") as f: return json.load(f)

    if pre_timed:
        with open(t_cache, "w", encoding="utf-8") as f: json.dump(pre_timed, f, ensure_ascii=False)
        return pre_timed

    g = gpu()
    words = []
    if not no_align:
        try:
            import whisperx
            print(f"⚙️ WhisperX alignment ({g.info()})…")
            audio = whisperx.load_audio(str(vocals))
            wmodel = whisperx.load_model(
                "large-v3", g.torch_device,
                compute_type=g.compute_type,
                language=lang,
            )

            # ШАГ A: транскрипция по реальному аудио → правильные тайминги сегментов
            # vad_options убраны — в новых версиях WhisperX этот параметр не поддерживается
            result = wmodel.transcribe(
                audio,
                batch_size=4 if g.backend == "cpu" else 16,
            )

            # ШАГ B: word-level alignment НА ТРАНСКРИПЦИИ (не на lyrics!)
            # wav2vec2 выравнивает то, что реально звучит → точные тайминги без дрейфа
            amodel, meta = whisperx.load_align_model(language_code=lang, device=g.torch_device)
            aligned = whisperx.align(
                result["segments"], amodel, meta,
                audio, g.torch_device,
                return_char_alignments=False,
            )

            aligned_words: list[dict] = []
            for seg in aligned["segments"]:
                for w in seg.get("words", []):
                    if text := w.get("word", "").strip():
                        aligned_words.append({
                            "word":  text,
                            "start": float(w.get("start", 0)),
                            "end":   float(w.get("end",   0)),
                        })

            # ШАГ C: ПОСЛЕ получения таймингов — заменяем слова на канонический текст
            # Тайминги остаются от реального аудио → рассинхрона нет
            if plain_lyrics and aligned_words:
                lyrics_words = [lw for line in plain_lyrics.splitlines()
                                for lw in line.split() if lw]
                if lyrics_words:
                    import difflib
                    sm = difflib.SequenceMatcher(
                        None,
                        [w["word"].lower() for w in aligned_words],
                        [lw.lower() for lw in lyrics_words],
                        autojunk=False,
                    )
                    result_words: list[dict] = []
                    for op, a0, a1, b0, b1 in sm.get_opcodes():
                        if op == "equal":
                            # Слова совпали → тайминг из alignment, текст из lyrics
                            for i in range(a1 - a0):
                                result_words.append({
                                    **aligned_words[a0 + i],
                                    "word": lyrics_words[b0 + i],
                                })
                        elif op == "replace":
                            # Разное кол-во → равномерно растягиваем тайминги
                            t_s = aligned_words[a0]["start"]
                            t_e = aligned_words[min(a1-1, len(aligned_words)-1)]["end"]
                            n   = b1 - b0
                            dur = (t_e - t_s) / max(n, 1)
                            for j, lw in enumerate(lyrics_words[b0:b1]):
                                result_words.append({
                                    "word":  lw,
                                    "start": t_s + j * dur,
                                    "end":   t_s + (j + 1) * dur,
                                })
                        elif op == "insert":
                            # Слово есть в lyrics, но Whisper не услышал (тихо/быстро)
                            ref_t = aligned_words[min(a0, len(aligned_words)-1)]["end"]
                            for j, lw in enumerate(lyrics_words[b0:b1]):
                                ts = ref_t + j * 0.2
                                result_words.append({"word": lw, "start": ts, "end": ts + 0.2})
                        # op == "delete": Whisper слышал лишнее (эдлиб) — пропускаем
                    words = result_words if result_words else aligned_words
                else:
                    words = aligned_words
            else:
                words = aligned_words

            print(f"   ✓ выровнено {len(words)} слов")
        except ImportError:
            print("   WhisperX не найден → Whisper STT")

    if not words:
        import whisper
        print(f"🗣 Whisper STT ({model_name}, {g.info()})…")
        model = whisper.load_model(model_name, device=g.torch_device)
        result = model.transcribe(str(vocals), word_timestamps=True, language=lang)
        for seg in result["segments"]:
            for w in seg.get("words", []):
                if t := w["word"].strip(): words.append({"word": t, "start": float(w["start"]), "end": float(w["end"])})
        words = phonetic_slang(apply_slang(words))

    with open(t_cache, "w", encoding="utf-8") as f: json.dump(words, f, ensure_ascii=False)
    return words

# ══════════════════════════════════════════════════════════════════════════════
#  РЕНДЕР
# ══════════════════════════════════════════════════════════════════════════════
_FM = _FS = None
def fonts():
    global _FM, _FS
    if _FM is None:
        cands = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        def load(sz):
            for p in cands:
                if os.path.exists(p): return ImageFont.truetype(p, sz)
            fp = Path(__file__).parent / "Roboto-Bold.ttf"
            if not fp.exists():
                print("⬇️ Скачиваем Roboto-Bold для кириллицы...")
                try: fp.write_bytes(requests.get("https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf", timeout=15).content)
                except: return ImageFont.load_default()
            return ImageFont.truetype(str(fp), sz)
        _FM, _FS = load(FONT_SIZE_MAIN), load(FONT_SIZE_SUB)
    return _FM, _FS

def current_pos(lines, t):
    cl, cw = 0, -1
    for li, line in enumerate(lines):
        for wi, w in enumerate(line):
            if w["start"] <= t: cl, cw = li, wi
    return cl, cw

def render_frame(lines, t, dur, bg_arr):
    fm, fs = fonts()
    img = Image.fromarray(bg_arr)
    d = ImageDraw.Draw(img)
    li, wi = current_pos(lines, t)
    cx, cy = WIDTH // 2, HEIGHT // 2 - (FONT_SIZE_MAIN + LINE_GAP) // 2

    def draw_line(line, y, awi, main_font, sub_font, state):
        parts, tw = [], 0
        for w in line:
            text = w["word"]
            is_adlib = text.startswith('(') or text.startswith('[')
            f = sub_font if is_adlib else main_font
            bx = f.getbbox(text + " ")
            pw = bx[2] - bx[0]
            parts.append({"text": text, "pw": pw, "is_adlib": is_adlib, "font": f})
            tw += pw

        x = cx - tw // 2
        for i, p in enumerate(parts):
            col = COLOR_CURRENT if i == awi and state == "current" else (COLOR_PAST if state == "past" or (state == "current" and i < awi) else COLOR_FUTURE)
            draw_y = y + (FONT_SIZE_MAIN - FONT_SIZE_SUB) if p["is_adlib"] and state == "current" else y
            d.text((x + 2, draw_y + 2), p["text"] + " ", font=p["font"], fill=(0, 0, 0, 200)) # Тень
            d.text((x, draw_y), p["text"] + " ", font=p["font"], fill=col)
            x += p["pw"]

    def at(idx, y, main):
        if 0 <= idx < len(lines):
            draw_line(lines[idx], y, wi if main else -2, fm if main else fs, fs, "current" if main else ("past" if idx < li else "future"))

    for off in range(CONTEXT_LINES, 0, -1): at(li - off, cy - off * (FONT_SIZE_SUB + LINE_GAP), False)
    at(li, cy, True)
    for off in range(1, CONTEXT_LINES + 1): at(li + off, cy + (FONT_SIZE_MAIN + LINE_GAP) + (off - 1) * (FONT_SIZE_SUB + LINE_GAP), False)

    by = HEIGHT - PROG_H - 4; p = t / dur if dur > 0 else 0
    d.rectangle([(0, by), (WIDTH, by + PROG_H)], fill=PROG_BG)
    d.rectangle([(0, by), (int(WIDTH * p), by + PROG_H)], fill=PROG_COLOR)
    return np.array(img)

def build_video(lines, no_vocals, output, duration, bg_video=None):
    from moviepy.editor import VideoClip, AudioFileClip, VideoFileClip
    print("🎬 Рендерим видео…")
    
    def make_default_bg():
        arr = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        for y in range(HEIGHT): arr[y] = [int(BG_TOP[i]*(1-y/HEIGHT)+BG_BOT[i]*(y/HEIGHT)) for i in range(3)]
        if SCANLINE_ALPHA:
            ov = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0)); d = ImageDraw.Draw(ov)
            for y in range(0, HEIGHT, 4): d.line([(0,y),(WIDTH,y)], fill=(0,0,0,SCANLINE_ALPHA))
            return np.array(Image.alpha_composite(Image.fromarray(arr).convert("RGBA"), ov).convert("RGB"))
        return arr
    
    default_bg = make_default_bg()
    bg_clip = VideoFileClip(str(bg_video)).without_audio().resize((WIDTH, HEIGHT)) if bg_video and Path(bg_video).exists() else None

    def get_bg_frame(t):
        if bg_clip: return (bg_clip.get_frame(t % bg_clip.duration) * 0.4).astype(np.uint8)
        return default_bg

    audio = AudioFileClip(str(no_vocals))
    dur = min(duration, audio.duration)
    clip = VideoClip(lambda t: render_frame(lines, t, dur, get_bg_frame(t)), duration=dur)
    clip = clip.set_fps(FPS).set_audio(audio.subclip(0, dur))
    clip.write_videofile(str(output), fps=FPS, codec="libx264", audio_codec="aac", temp_audiofile=str(output.parent/"_tmp.m4a"), remove_temp=True, logger="bar")
    print(f"\n✅ Готово: {output}")

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def guess_meta(fname: str) -> tuple[str, str]:
    stem = Path(fname).stem.strip()

    # 1. Отрезаем "NA - " от yt-dlp В ПЕРВУЮ ОЧЕРЕДЬ
    if stem.upper().startswith("NA - "):
        stem = stem[5:].strip()

    # 2. Массив регулярных выражений для тотальной зачистки
    junk_patterns = [
        # Стандартные приписки клипов и аудио
        r'\((?:official\s+)?(?:music\s+)?video\)',
        r'\((?:official\s+)?audio\)',
        r'\((?:official\s+)?lyrics?(?:\s+video)?\)',
        r'\(visualizer\)',
        r'\(live(?:.*?)?\)', # Всё что содержит (live...)
        
        # Тотальная зачистка квадратных, фигурных и азиатских скобок (там обычно каналы, релизы, теги)
        r'\[.*?\]',
        r'【.*?】',
        r'\{.*?\}',
        
        # Ссылки на паблики (частая болезнь треков из VK/Telegram)
        r'(?i)vk\.com/\S+',
        r'(?i)t\.me/\S+',
        
        # Информация о качестве (битрейт, разрешение)
        r'(?i)\(?(?:320|128|192)\s*kbps\)?',
        r'(?i)\(?(?:1080p|720p|4k|hd|hq)\)?',
        
        # Хвосты после вертикальных черт
        r'\s*[|｜].*',
        
        # Дублирующиеся расширения
        r'\.(?:mp3|wav|flac|m4a|ogg)$'
    ]
    
    # Применяем все фильтры по очереди (с игнором регистра)
    for pattern in junk_patterns:
        stem = re.sub(pattern, '', stem, flags=re.IGNORECASE)

    # 3. Убираем лишние пробелы, которые остались после вырезания кусков
    stem = re.sub(r'\s+', ' ', stem).strip()

    # 4. Стандартизируем разные виды тире
    stem = re.sub(r'\s*—\s*|\s*–\s*|\s*~\s*', ' - ', stem)

    # 5. Пытаемся разделить на Артиста и Название
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        artist = artist.strip()
        title = title.strip()
        
        # yt-dlp иногда ставит заглушки вместо автора, фильтруем их
        if artist.lower() in ["na", "various artists", "unknown artist", "topic", "release"]:
            return "", title
            
        return artist, title

    # 6. Если тире так и не нашлось, считаем всё названием (заменив нижние подчеркивания)
    stem = re.sub(r'[_-]', ' ', stem)
    stem = re.sub(r'\s+', ' ', stem).strip()
    
    return "", stem

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--artist", "-a", default=None)
    ap.add_argument("--title",  "-t", default=None)
    ap.add_argument("--output", "-o", default=None)
    ap.add_argument("--bg-video", "-bg", default=None, help="Фоновое видео .mp4")
    ap.add_argument("--model",  "-m", default="medium", choices=["tiny","base","small","medium","large","large-v3"])
    ap.add_argument("--lang",   "-l", default="ru")
    ap.add_argument("--words-per-line", "-w", type=int, default=WORDS_PER_LINE)
    ap.add_argument("--no-align",  action="store_true")
    ap.add_argument("--no-search", action="store_true")
    args = ap.parse_args()

    inp = Path(args.input).resolve()
    ga, gt = guess_meta(args.input)
    artist, title = args.artist or ga, args.title or gt
    out = Path(args.output) if args.output else inp.parent / (inp.stem + "_karaoke.mp4")

    print(f"🖥 Железо: {gpu().info()}\n")
    
    file_hash = get_file_hash(inp)
    print(f"🔖 Хэш трека: {file_hash[:8]}")

    vocals, no_vocals = separate_stems(inp, file_hash)
    
    # Сначала проверяем, есть ли тайминги в кэше. Если есть — скипаем поиск текста!
    t_cache = CACHE_DIR / f"{file_hash}_timings.json"
    pre_timed, plain_lyrics = None, None
    if not t_cache.exists() and not args.no_search:
        pre_timed, plain_lyrics = find_lyrics(artist, title)

    words = get_timings(vocals, file_hash, pre_timed, plain_lyrics, args.model, args.lang, args.no_align)
    if not words:
        print("❌ Не удалось получить тайминги."); sys.exit(1)

    lines = [words[i:i+args.words_per_line] for i in range(0, len(words), args.words_per_line)]
    build_video(lines, no_vocals, out, words[-1]["end"] + 1.0, args.bg_video)

if __name__ == "__main__":
    main()
