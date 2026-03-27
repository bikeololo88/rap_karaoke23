#!/usr/bin/env python3
"""
Rap Karaoke — GUI App
=====================
Полноценное приложение: очередь, лидерборд, микрофон, оценка,
пульсирующий фон, голосовые команды, скачивание через yt-dlp.

Зависимости (к существующим из rap_karaoke.py):
    pip install PyQt6 sounddevice soundfile yt-dlp

Запуск:
    python rap_karaoke_app.py

rap_karaoke.py должен лежать рядом.
"""

import sys, os, re, json, time, threading, subprocess, hashlib, shutil
from pathlib import Path
from typing import Optional
from datetime import datetime
from collections import deque
import numpy as np

# ── PyQt6 ──────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QTextEdit, QProgressBar, QSplitter,
    QFileDialog, QMessageBox, QLineEdit, QComboBox, QCheckBox,
    QGroupBox, QTabWidget, QStatusBar, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRect, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QPainterPath, QFontMetrics, QKeyEvent,
)

# ── Audio ───────────────────────────────────────────────────────────────────
try:
    import soundfile as sf
except ImportError:
    print("⚠️  soundfile не установлен — pip install soundfile")

AUDIO_OK = False
if 'sf' in locals():
    try:
        import sounddevice as sd
        AUDIO_OK = True
    except Exception as e:
        print(f"⚠️ Ошибка инициализации sounddevice: {e}")
        print("   Микрофон и воспроизведение в реальном времени (GUI) отключены.")

# ── Backend ─────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
try:
    import rap_karaoke as bk
    BACKEND_OK = True
except ImportError:
    BACKEND_OK = False
    print("⚠️  rap_karaoke.py не найден рядом с приложением!")

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS & STYLE
# ══════════════════════════════════════════════════════════════════════════════
APP_DIR = Path.home() / ".cache" / "rap_karaoke"
KARAOKE_VIDEOS_DIR = Path.home() / "Karaoke"
DOWNLOADS_DIR = KARAOKE_VIDEOS_DIR / "Downloads"

APP_DIR.mkdir(parents=True, exist_ok=True)
KARAOKE_VIDEOS_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)

LEADERBOARD_FILE = APP_DIR / "leaderboard.json"
QUEUE_FILE       = APP_DIR / "queue.json"
SETTINGS_FILE    = APP_DIR / "settings.json"

DARK_STYLE = """
QMainWindow, QDialog, QWidget {
    background-color: #10121c;
    color: #e0e0f4;
    font-family: 'DejaVu Sans', 'Noto Sans', Arial, sans-serif;
    font-size: 13px;
}
QPushButton {
    background-color: #16162a;
    color: #e0e0f4;
    border: 1px solid #2e2e55;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover  { background-color: #20203a; border-color: #ffdc28; color: #ffdc28; }
QPushButton:pressed { background-color: #ffdc28; color: #08080f; }
QPushButton:disabled { color: #3a3a5a; border-color: #1a1a2e; }
QPushButton:checked { background-color: #ffdc28; color: #08080f; border-color: #ffdc28; }
QSlider::groove:horizontal { height:4px; background:#2a2a45; border-radius:2px; }
QSlider::handle:horizontal { width:15px; height:15px; background:#ffdc28; border-radius:7px; margin:-5px 0; }
QSlider::sub-page:horizontal { background:#ffdc28; border-radius:2px; }
QListWidget {
    background:#141424; border:1px solid #2e2e55; border-radius:6px; color:#e0e0f4;
    outline: none;
}
QListWidget::item { padding: 5px 8px; }
QListWidget::item:selected { background:#20203a; color:#ffdc28; }
QListWidget::item:hover { background:#16162a; }
QLabel { color: #e0e0f4; }
QLineEdit {
    background:#141424; border:1px solid #2e2e55; border-radius:6px;
    padding:6px 10px; color:#e0e0f4;
}
QLineEdit:focus { border-color: #ffdc28; }
QTextEdit { background:#141424; border:1px solid #2e2e55; color:#e0e0f4; border-radius:6px; }
QProgressBar {
    border:1px solid #2e2e55; border-radius:4px; background:#0c0c1c;
    color:#e0e0f4; text-align:center; height:18px;
}
QProgressBar::chunk { background:#ffdc28; border-radius:3px; }
QTabWidget::pane   { border:1px solid #2e2e55; border-radius:0 6px 6px 6px; }
QTabBar::tab       { background:#12122a; color:#888; padding:8px 18px; margin-right:2px; border-radius:4px 4px 0 0; }
QTabBar::tab:selected { background:#20203a; color:#ffdc28; }
QTabBar::tab:hover    { background:#16162a; color:#ccc; }
QComboBox {
    background:#16162a; border:1px solid #2e2e55; border-radius:6px;
    padding:5px 10px; color:#e0e0f4;
}
QComboBox::drop-down { border:none; }
QComboBox QAbstractItemView { background:#141424; color:#e0e0f4; selection-background-color:#20203a; }
QGroupBox { border:1px solid #2e2e55; border-radius:6px; margin-top:12px; padding:10px; color:#888; }
QGroupBox::title   { subcontrol-origin:margin; left:12px; padding:0 4px; color:#aaa; }
QScrollBar:vertical { width:8px; background:#0c0c1c; }
QScrollBar::handle:vertical { background:#2e2e55; border-radius:4px; min-height:20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QSplitter::handle { background:#2e2e55; }
QStatusBar { background:#0c0c1c; color:#666; border-top:1px solid #1a1a2e; }
"""


# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"model": "medium", "lang": "ru", "words_per_line": 6, "player_name": "Player 1"}

def save_settings(s: dict):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO ENGINE  (sounddevice, real-time mixing)
# ══════════════════════════════════════════════════════════════════════════════
class AudioEngine:
    def __init__(self):
        self._inst: Optional[np.ndarray] = None
        self._voc:  Optional[np.ndarray] = None
        self.sr = 44100
        self._pos = 0
        self._playing = False
        self._lock = threading.Lock()
        self.vol_inst = 1.0
        self.vol_voc  = 0.15       # тихая подсказка по умолчанию
        self._stream: Optional["sd.OutputStream"] = None
        self.on_finished: Optional[callable] = None

    def load(self, voc_path: Path, inst_path: Path):
        v, sr = sf.read(str(voc_path),  dtype="float32")
        i, _  = sf.read(str(inst_path), dtype="float32")
        self.sr = sr
        def stereo(a):
            return np.stack([a, a], axis=1) if a.ndim == 1 else a
        v, i = stereo(v), stereo(i)
        n = min(len(v), len(i))
        self._voc, self._inst = v[:n], i[:n]
        self._pos = 0

    def _cb(self, outdata, frames, time_info, status):
        # Ни в коем случае нельзя использовать print() внутри аудио-коллбэка!
        # Это блокирует поток I/O и вызывает каскадный эффект "output underflow".
        # if status: pass 

        with self._lock:
            # By default, fill with silence
            outdata.fill(0)

            if self._playing and self._inst is not None:
                remaining = len(self._inst) - self._pos
                if remaining == 0:
                    if self._playing:
                        self._playing = False # Signal to _tick timer to stop the stream
                    return

                chunk_size = min(frames, remaining)
                outdata[:chunk_size] = np.clip(
                    self._inst[self._pos : self._pos + chunk_size] * self.vol_inst +
                    self._voc[self._pos : self._pos + chunk_size] * self.vol_voc, 
                    -1.0, 1.0)
                self._pos += chunk_size

    def play(self):
        if not AUDIO_OK or self._inst is None: return
        if self._stream: self._stream.close()
        self._stream = sd.OutputStream(
            samplerate=self.sr, channels=2,
            callback=self._cb, dtype="float32",
            blocksize=8192, latency="high")  # Даем гигантский буфер, чтобы графика не душила звук
        self._playing = True
        self._stream.start()

    def pause(self):
        with self._lock: self._playing = not self._playing

    def stop(self):
        with self._lock: self._playing = False; self._pos = 0
        if self._stream: self._stream.close(); self._stream = None

    def seek(self, sec: float):
        with self._lock: self._pos = max(0, int(sec * self.sr))

    @property
    def position(self) -> float: 
        # Вычитаем задержку буфера звуковой карты, чтобы закраска текста не бежала впереди музыки
        # Значение latency от sounddevice не всегда идеально точное.
        # Добавляем небольшой фиксированный оффсет (70мс), чтобы компенсировать
        # неточности драйвера и прочие задержки в системе.
        latency = self._stream.latency if self._stream else 0.0
        return max(0.0, (self._pos / max(self.sr, 1)) - (latency + 0.07))
    @property
    def duration(self)  -> float: return (len(self._inst) / self.sr) if self._inst is not None else 0
    @property
    def is_playing(self) -> bool: return self._playing


# ══════════════════════════════════════════════════════════════════════════════
#  MIC ENGINE
# ══════════════════════════════════════════════════════════════════════════════
class MicEngine:
    SR = 22050
    def __init__(self):
        self._buf     = deque(maxlen=self.SR * 5)
        self._rms_buf = deque(maxlen=500)
        self._stream  = None
        self.active   = False
        self._lock    = threading.Lock()

    def _cb(self, indata, frames, ti, st):
        mono = indata[:,0] if indata.ndim > 1 else indata.ravel()
        with self._lock:
            self._buf.extend(mono.tolist())
            self._rms_buf.append(float(np.sqrt(np.mean(mono**2))))

    def start(self):
        if not AUDIO_OK: return
        try:
            self._stream = sd.InputStream(
                samplerate=self.SR, channels=1, dtype="float32",
                blocksize=512, callback=self._cb)
            self._stream.start(); self.active = True
        except Exception as e: print(f"Mic: {e}")

    def stop(self):
        if self._stream: self._stream.close(); self._stream = None
        self.active = False

    def waveform(self, n=200) -> np.ndarray:
        with self._lock: data = np.array(list(self._buf)[-n*20:])
        if len(data) < 10: return np.zeros(n)
        step = max(1, len(data)//n)
        return data[::step][:n]

    def rms_window(self, n=60) -> np.ndarray:
        with self._lock: d = list(self._rms_buf)[-n:]
        return np.array(d) if d else np.zeros(n)

    def rms(self) -> float:
        with self._lock: return float(self._rms_buf[-1]) if self._rms_buf else 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  SCORER  (ритм-корреляция: бугры и горки вокальной дорожки vs микрофон)
# ══════════════════════════════════════════════════════════════════════════════
class Scorer:
    """
    Оценивает пение по двум компонентам:
    1. Ритм (40%): Pearson-корреляция энергетических огибающих mic vs вокал.
       Улавливает совпадение динамики/пульсации.
    2. Покрытие (60%): доля слов, во время которых mic активен (RMS > порог).
       Улавливает «пел ли вообще» в нужные моменты.

    Итоговый балл = 0.4×ритм + 0.6×покрытие, отображается 0..100.
    """
    ENV_SR   = 100   # точек огибающей в секунду
    MIC_THRES = 0.01  # порог RMS «поёт / не поёт»

    def __init__(self):
        self.vocal_env: Optional[np.ndarray] = None
        self._rhythm_scores:   list[float] = []
        self._coverage_scores: list[float] = []
        self._word_hits:  int = 0
        self._word_total: int = 0
        self._words: list = []   # список слов для coverage

    def load_vocal(self, path: Path):
        try:
            data, sr = sf.read(str(path), dtype="float32")
            if data.ndim > 1: data = data.mean(1)
            hop = sr // self.ENV_SR
            self.vocal_env = np.array([
                float(np.sqrt(np.mean(data[i:i+hop]**2)))
                for i in range(0, len(data)-hop, hop)
            ], dtype=np.float32)
            m = self.vocal_env.max()
            if m > 0: self.vocal_env /= m
        except Exception as e:
            print(f"Scorer: {e}"); self.vocal_env = None

    def set_words(self, words: list):
        """Передаём список слов с таймингами для покрытия."""
        self._words = words

    def score_tick(self, mic_rms_window: np.ndarray, pos: float) -> tuple[float, float]:
        """Возвращает (ритм 0-100, покрытие 0-100)."""
        # --- Ритм ---
        rhythm = 0.0
        if self.vocal_env is not None and len(mic_rms_window) >= 5:
            c  = int(pos * self.ENV_SR)
            h  = len(mic_rms_window) // 2
            v  = self.vocal_env[max(0, c-h): min(len(self.vocal_env), c+h)]
            n  = min(len(mic_rms_window), len(v))
            if n >= 5:
                m, vv = mic_rms_window[:n], v[:n]
                m  = m  / (m.max()  + 1e-9)
                vv = vv / (vv.max() + 1e-9)
                if np.std(m) > 1e-6 and np.std(vv) > 1e-6:
                    rhythm = max(0.0, float(np.corrcoef(m, vv)[0,1])) * 100.0
        self._rhythm_scores.append(rhythm)

        # --- Покрытие: проверяем слова вокруг текущей позиции ---
        cov = 0.0
        if self._words:
            window_words = [w for w in self._words
                            if w["start"] <= pos <= w.get("end", pos+0.1)]
            if window_words:
                active = float(np.mean(mic_rms_window[-10:])) > self.MIC_THRES if len(mic_rms_window) >= 10 else False
                self._word_total += len(window_words)
                if active: self._word_hits += len(window_words)
            cov = (self._word_hits / max(1, self._word_total)) * 100.0
        self._coverage_scores.append(cov)
        return rhythm, cov

    # Kept for backwards compat (ProcessingThread uses old .score())
    def score(self, mic_rms: np.ndarray, pos: float) -> float:
        r, c = self.score_tick(mic_rms, pos)
        return r * 0.4 + c * 0.6

    @property
    def session(self) -> float:
        r = float(np.mean(self._rhythm_scores))  if self._rhythm_scores  else 0.0
        c = float(np.mean(self._coverage_scores)) if self._coverage_scores else 0.0
        return r * 0.4 + c * 0.6

    @property
    def rhythm_avg(self) -> float:
        return float(np.mean(self._rhythm_scores)) if self._rhythm_scores else 0.0

    @property
    def coverage_avg(self) -> float:
        return float(np.mean(self._coverage_scores)) if self._coverage_scores else 0.0

    def reset(self):
        self._rhythm_scores.clear(); self._coverage_scores.clear()
        self._word_hits = 0; self._word_total = 0


# ══════════════════════════════════════════════════════════════════════════════
#  LEADERBOARD & QUEUE
# ══════════════════════════════════════════════════════════════════════════════
class Leaderboard:
    def __init__(self):
        self.data: dict = {}
        if LEADERBOARD_FILE.exists():
            try:
                with open(LEADERBOARD_FILE) as f: self.data = json.load(f)
            except: pass

    def save(self):
        with open(LEADERBOARD_FILE,'w') as f: json.dump(self.data,f,ensure_ascii=False,indent=2)

    def add(self, track_hash: str, track_name: str, player: str, score: float):
        if track_hash not in self.data:
            self.data[track_hash] = {"name": track_name, "scores": []}
        self.data[track_hash]["scores"].append({
            "player": player, "score": round(score,1),
            "date": datetime.now().strftime("%d.%m %H:%M")
        })
        self.data[track_hash]["scores"].sort(key=lambda x:x["score"],reverse=True)
        self.data[track_hash]["scores"] = self.data[track_hash]["scores"][:10]
        self.save()

    def all_scores(self) -> list[dict]:
        out = []
        for h, e in self.data.items():
            for s in e["scores"]: out.append({**s,"track":e["name"]})
        return sorted(out,key=lambda x:x["score"],reverse=True)

    def track_scores(self, h: str) -> list[dict]:
        return self.data.get(h,{}).get("scores",[])


class TrackQueue:
    def __init__(self):
        self.items: list[dict] = []
        self.current = 0
        self._load()

    def _load(self):
        if QUEUE_FILE.exists():
            try:
                d = json.load(open(QUEUE_FILE))
                self.items   = [i for i in d.get("items",[]) if Path(i.get("path","")).exists()]
                self.current = d.get("current",0)
            except: pass

    def save(self):
        with open(QUEUE_FILE,'w') as f:
            json.dump({"items":self.items,"current":self.current},f,ensure_ascii=False)

    def add(self, path:str, artist:str="", title:str="") -> dict:
        # Теперь используем ту же самую функцию хэширования, что и бэкенд
        if BACKEND_OK:
            h = bk.get_file_hash(Path(path))
        else:
            h = hashlib.md5(open(path,'rb').read(65536)).hexdigest()[:8]
            
        item = {"path":path,"artist":artist,"title":title or Path(path).stem,"hash":h}
        self.items.append(item); self.save(); return item

    def remove(self, idx:int):
        if 0 <= idx < len(self.items):
            self.items.pop(idx)
            self.current = min(self.current, max(0,len(self.items)-1))
            self.save()

    def move(self, idx:int, delta:int):
        j = idx+delta
        if 0 <= idx < len(self.items) and 0 <= j < len(self.items):
            self.items[idx],self.items[j] = self.items[j],self.items[idx]
            self.save()

    def current_item(self) -> Optional[dict]:
        return self.items[self.current] if self.items and self.current < len(self.items) else None

    def is_processed(self, item:dict) -> bool:
        h = item.get("hash","")
        return bool(h) and (APP_DIR/f"{h}_vocals.wav").exists() and (APP_DIR/f"{h}_timings.json").exists()


# ══════════════════════════════════════════════════════════════════════════════
#  LYRICS CANDIDATES  (LRCLIB → Genius → amalgama)
# ══════════════════════════════════════════════════════════════════════════════
def fetch_candidates(artist:str, title:str, progress_cb: Optional[callable] = None) -> list[dict]:
    if not BACKEND_OK: return []
    out = []
    # 1. LRCLIB — несколько результатов с синхронными LRC
    try:
        r = bk._req("https://lrclib.net/api/search",
                    params={"track_name":title,"artist_name":artist})
        if r:
            if progress_cb: progress_cb("     ✓ LRCLIB: найдено")
            for h in (r.json() or [])[:5]:
                words = bk._parse_lrc(h["syncedLyrics"]) if h.get("syncedLyrics") else []
                plain = (h.get("plainLyrics") or "").strip()
                if words or plain:
                    out.append({
                        "source": "LRCLIB",
                        "title":  h.get("trackName",title),
                        "artist": h.get("artistName",artist),
                        "synced": bool(words),
                        "words":  words,
                        "plain":  plain,
                        "preview":(plain or "")[:350],
                    })
            else:
                if progress_cb: progress_cb("     ✗ LRCLIB: нет результатов")
        else:
            if progress_cb: progress_cb("     ✗ LRCLIB: ошибка запроса")
    except: pass
    # 2. Genius
    if len(out) < 4:
        try:
            r = bk._req("https://genius.com/api/search/multi",params={"q":f"{artist} {title}"})
            if r:
                if progress_cb: progress_cb("     ✓ Genius: найдено")
                for hit in r.json().get("response",{}).get("sections",[{}])[0].get("hits",[])[:3]:
                    res  = hit.get("result",{})
                    page = bk._req("https://genius.com"+res.get("path",""))
                    if page:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(page.text,"html.parser")
                        cs   = soup.find_all("div",attrs={"data-lyrics-container":"true"})
                        if cs:
                            plain = bk._clean("\n".join(c.get_text("\n") for c in cs))
                            if len(plain) > 80:
                                out.append({
                                    "source":"Genius",
                                    "title": res.get("title",title),
                                    "artist":res.get("primary_artist",{}).get("name",artist),
                                    "synced":False,"words":[],"plain":plain,
                                    "preview":plain[:350],
                                })
                else:
                    if progress_cb: progress_cb("     ✗ Genius: нет результатов")
            else:
                if progress_cb: progress_cb("     ✗ Genius: ошибка запроса")
        except: pass
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  THREADS
# ══════════════════════════════════════════════════════════════════════════════
class ProcessingThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, item:dict, settings:dict):
        super().__init__()
        self.item     = item
        self.settings = settings
        self._cancel  = False

    def cancel(self): self._cancel = True

    def run(self):
        try:
            path  = Path(self.item["path"])
            h     = bk.get_file_hash(path)
            artist= self.item.get("artist","")
            title = self.item.get("title",path.stem)
            model = self.settings.get("model","medium")
            lang  = self.settings.get("lang","ru")

            self.progress.emit("🎛  Разделяем вокал и минус (UVR)…")
            if self._cancel: return
            voc, inst = bk.separate_stems(path, h)

            self.progress.emit("🔍  Ищем текст песни…")
            if self._cancel: return
            candidates = fetch_candidates(artist, title, progress_cb=self.progress.emit)

            self.progress.emit("⚙️  Выравниваем тайминги слов…")
            if self._cancel: return
            pre_timed = candidates[0]["words"] if candidates and candidates[0].get("words") else None
            plain     = candidates[0]["plain"]  if candidates else None
            words = bk.get_timings(voc, h, pre_timed, plain, model, lang, no_align=False)

            if not words:
                self.error.emit("Не удалось получить тайминги слов"); return

            self.finished.emit({
                "vocals":      str(voc),
                "instrumental":str(inst),
                "words":       words,
                "candidates":  candidates,
                "file_hash":   h,
                "artist":      artist,
                "title":       title,
            })
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()[-600:]}")


class SearchThread(QThread):
    """Ищет несколько вариантов на YT без скачивания."""
    results  = pyqtSignal(list)   # list of dicts
    error    = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            r = subprocess.run(
                ["yt-dlp", f"ytsearch8:{self.query}",
                 "--flat-playlist", "--dump-json", "--no-playlist"],
                capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                self.error.emit(r.stderr[-200:]); return
            items = []
            for line in r.stdout.strip().splitlines():
                try:
                    d = json.loads(line)
                    dur = d.get("duration") or 0
                    mins, secs = divmod(int(dur), 60)
                    items.append({
                        "id":      d.get("id",""),
                        "url":     d.get("url") or f"https://www.youtube.com/watch?v={d.get('id','')}",
                        "title":   d.get("title","?"),
                        "channel": d.get("channel") or d.get("uploader",""),
                        "duration":f"{mins}:{secs:02d}",
                        "views":   d.get("view_count", 0),
                    })
                except: pass
            self.results.emit(items)
        except FileNotFoundError:
            self.error.emit("yt-dlp не установлен:\npip install yt-dlp")
        except Exception as e:
            self.error.emit(str(e))


class DownloadThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, url_or_query: str, out_dir: str, is_url: bool = False):
        super().__init__()
        self.url_or_query = url_or_query
        self.out_dir      = out_dir
        self.is_url       = is_url

    def run(self):
        try:
            target = self.url_or_query if self.is_url else f"ytsearch1:{self.url_or_query}"
            self.progress.emit(f"⬇️  Скачиваем…")
            tmpl = str(Path(self.out_dir) / "%(artist)s - %(title)s.%(ext)s")
            r = subprocess.run(
                ["yt-dlp", target,
                 "-x","--audio-format","mp3","--audio-quality","0",
                 "-o", tmpl, "--print","after_move:filepath","--no-playlist"],
                capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                self.error.emit(r.stderr[-300:]); return
            filepath = (r.stdout.strip().splitlines() or [""])[-1]
            if filepath and Path(filepath).exists():
                self.finished.emit(filepath)
            else:
                self.error.emit("Файл не найден после загрузки")
        except FileNotFoundError:
            self.error.emit("yt-dlp не установлен:\npip install yt-dlp")
        except Exception as e:
            self.error.emit(str(e))


class VoiceThread(QThread):
    """Push-to-talk: записывает N секунд и транскрибирует через Whisper tiny."""
    recognized = pyqtSignal(str)

    def __init__(self, duration:float=5.0):
        super().__init__()
        self.duration = duration

    def run(self):
        if not AUDIO_OK:
            self.recognized.emit("❌ sounddevice не установлен"); return
        try:
            import whisper
            self.recognized.emit("⏺ Идёт запись…")
            audio = sd.rec(int(self.duration*16000),samplerate=16000,channels=1,dtype="float32")
            sd.wait()
            self.recognized.emit("🤔 Распознаём…")
            model = whisper.load_model("tiny")
            result = model.transcribe(audio.ravel(), language="ru", fp16=False)
            self.recognized.emit(result["text"].strip())
        except Exception as e:
            self.recognized.emit(f"❌ {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  DIALOGS
# ══════════════════════════════════════════════════════════════════════════════
class LyricsConfirmDialog(QDialog):
    """Показывает несколько вариантов текста, пользователь выбирает нужный."""
    def __init__(self, candidates:list[dict], artist:str, title:str, parent=None):
        super().__init__(parent)
        self.candidates = candidates
        self.selected   = candidates[0] if candidates else None
        self.setWindowTitle(f"📝 Текст: {artist} — {title}")
        self.setMinimumSize(750, 520)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lbl = QLabel("Найдены варианты текста. Выбери нужный или нажми «Без текста»:")
        lbl.setStyleSheet("color:#ffdc28; font-size:14px;")
        lay.addWidget(lbl)

        spl = QSplitter(Qt.Orientation.Horizontal)

        # Левая — список
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0)
        ll.addWidget(QLabel("Варианты:"))
        self.lst = QListWidget()
        for c in self.candidates:
            icon = "⚡" if c["synced"] else "📝"
            self.lst.addItem(f"{icon} [{c['source']}] {c['artist']} — {c['title']}")
        if self.candidates: self.lst.setCurrentRow(0)
        self.lst.currentRowChanged.connect(self._preview)
        ll.addWidget(self.lst)
        skip = QPushButton("🔇 Без текста (только STT)")
        skip.clicked.connect(self._skip)
        ll.addWidget(skip)
        spl.addWidget(left)

        # Правая — превью
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0)
        rl.addWidget(QLabel("Превью текста:"))
        self.preview = QTextEdit(); self.preview.setReadOnly(True)
        rl.addWidget(self.preview)
        spl.addWidget(right)
        spl.setSizes([300, 450])
        lay.addWidget(spl)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._ok)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        if self.candidates: self._preview(0)

    def _preview(self, row:int):
        if 0 <= row < len(self.candidates):
            self.preview.setText(self.candidates[row]["preview"])

    def _ok(self):
        r = self.lst.currentRow()
        self.selected = self.candidates[r] if 0 <= r < len(self.candidates) else None
        self.accept()

    def _skip(self):
        self.selected = None; self.accept()


class ProcessingDialog(QDialog):
    """Запускает ProcessingThread, показывает прогресс, кнопку Отмена."""
    def __init__(self, item:dict, settings:dict, parent=None):
        super().__init__(parent)
        self.result_data = None
        self._thread = ProcessingThread(item, settings)
        self._thread.progress.connect(self._prog)
        self._thread.finished.connect(self._done)
        self._thread.error.connect(self._err)
        self.setWindowTitle(f"⚙️  {item.get('title','Обработка…')}")
        self.setModal(True); self.setMinimumSize(500, 220)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        self.title_lbl = QLabel("Готовим трек для карaоке…")
        self.title_lbl.setStyleSheet("font-size:15px; color:#ffdc28; font-weight:bold;")
        lay.addWidget(self.title_lbl)

        self.status_lbl = QLabel("Инициализация…"); self.status_lbl.setWordWrap(True)
        lay.addWidget(self.status_lbl)

        self.bar = QProgressBar(); self.bar.setRange(0,0)
        lay.addWidget(self.bar)

        if BACKEND_OK:
            g = bk.gpu()
            lay.addWidget(QLabel(g.info()))

        cancel = QPushButton("❌  Отмена")
        cancel.clicked.connect(self._cancel)
        lay.addWidget(cancel)

    def showEvent(self, e):
        super().showEvent(e); self._thread.start()

    def _prog(self, msg): self.status_lbl.setText(msg)

    def _done(self, data:dict):
        self.result_data = data; self.accept()

    def _err(self, err):
        QMessageBox.critical(self,"Ошибка обработки", err[:600])
        self.reject()

    def _cancel(self):
        self._thread.cancel(); self._thread.quit(); self.reject()


class DownloadDialog(QDialog):
    """
    Диалог скачивания: сначала ищет 8 вариантов на YT, показывает
    список (название, канал, длительность), потом скачивает выбранный.
    """
    track_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⬇️  Найти и скачать трек")
        self.setMinimumSize(680, 480)
        self._out      = str(DOWNLOADS_DIR)
        self._results  = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        # Search bar
        top = QHBoxLayout()
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Платина — Санта Клаус  /  PHARAOH Дико, например…")
        self.inp.returnPressed.connect(self._search)
        top.addWidget(self.inp)
        self.search_btn = QPushButton("🔍 Найти")
        self.search_btn.setFixedWidth(90)
        self.search_btn.clicked.connect(self._search)
        top.addWidget(self.search_btn)
        lay.addLayout(top)

        # Status + bar
        self.status = QLabel("Введи запрос и нажми «Найти»")
        self.status.setStyleSheet("color:#888; font-size:12px;")
        lay.addWidget(self.status)
        self.bar = QProgressBar(); self.bar.setRange(0,0); self.bar.hide()
        lay.addWidget(self.bar)

        # Results list
        lbl = QLabel("Результаты (выбери нужный вариант):")
        lay.addWidget(lbl)
        self.lst = QListWidget()
        self.lst.setAlternatingRowColors(True)
        self.lst.setStyleSheet(
            "QListWidget { alternate-background-color: #12122a; }"
            "QListWidget::item { padding: 6px 10px; border-bottom: 1px solid #1e1e38; }"
        )
        self.lst.itemDoubleClicked.connect(self._download_selected)
        lay.addWidget(self.lst)

        # Buttons
        row = QHBoxLayout()
        self.dl_btn = QPushButton("⬇️  Скачать выбранный")
        self.dl_btn.setEnabled(False)
        self.dl_btn.clicked.connect(self._download_selected)
        cl = QPushButton("Закрыть")
        cl.clicked.connect(self.close)
        row.addWidget(self.dl_btn); row.addWidget(cl)
        lay.addLayout(row)

    def _search(self):
        q = self.inp.text().strip()
        if not q: return
        self.lst.clear(); self._results = []
        self.dl_btn.setEnabled(False)
        self.bar.show()
        self.status.setText(f"🔍 Ищем «{q}» на YouTube…")
        self._st = SearchThread(q)
        self._st.results.connect(self._on_results)
        self._st.error.connect(lambda e: (self.bar.hide(), self.status.setText(f"❌ {e[:200]}")))
        self._st.start()

    def _on_results(self, items: list):
        self.bar.hide()
        self._results = items
        self.lst.clear()
        if not items:
            self.status.setText("Ничего не найдено, попробуй другой запрос")
            return
        self.status.setText(f"Найдено вариантов: {len(items)}. Двойной клик или «Скачать».")
        for it in items:
            views = f"{it['views']//1000}K" if it['views'] > 1000 else str(it['views'])
            self.lst.addItem(
                f"🎵  {it['title']}\n"
                f"    📺 {it['channel']}  ⏱ {it['duration']}  👁 {views}"
            )
        self.lst.setCurrentRow(0)
        self.dl_btn.setEnabled(True)

    def _download_selected(self):
        row = self.lst.currentRow()
        if row < 0 or row >= len(self._results): return
        it = self._results[row]
        self.dl_btn.setEnabled(False)
        self.search_btn.setEnabled(False)
        self.bar.show()
        self.status.setText(f"⬇️ Скачиваем: {it['title'][:60]}…")
        self._dt = DownloadThread(it["url"], self._out, is_url=True)
        self._dt.progress.connect(self.status.setText)
        self._dt.finished.connect(self._on_done)
        self._dt.error.connect(lambda e: (
            self.bar.hide(),
            self.status.setText(f"❌ {e[:200]}"),
            self.dl_btn.setEnabled(True),
            self.search_btn.setEnabled(True),
        ))
        self._dt.start()

    def _on_done(self, path: str):
        self.bar.hide()
        self.status.setText(f"✅ Скачано: {Path(path).name}")
        self.dl_btn.setEnabled(True)
        self.search_btn.setEnabled(True)
        self.track_ready.emit(path)


class RenderThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, data: dict, wpl: int, out_path: Path):
        super().__init__()
        self.data = data
        self.wpl = wpl
        self.out_path = out_path

    def run(self):
        try:
            lines = [self.data["words"][i:i+self.wpl] for i in range(0, len(self.data["words"]), self.wpl)]
            duration = self.data["words"][-1]["end"] + 1.0 if self.data["words"] else 0
            # Вызываем функцию рендера из бэкенда
            bk.build_video(lines, Path(self.data["instrumental"]), self.out_path, duration)
            self.finished.emit(str(self.out_path))
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()[-600:]}")


class RenderDialog(QDialog):
    def __init__(self, data: dict, wpl: int, out_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎬 Сохранение видео")
        self.setModal(True)
        self.setMinimumSize(400, 150)
        self.out_path = out_path

        lay = QVBoxLayout(self)
        self.lbl = QLabel(f"Рендерим MP4 файл...\n{out_path.name}")
        self.lbl.setStyleSheet("font-size:14px; color:#ffdc28;")
        lay.addWidget(self.lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0) # Бесконечная анимация загрузки
        lay.addWidget(self.bar)

        self._thread = RenderThread(data, wpl, out_path)
        self._thread.finished.connect(self.accept)
        self._thread.error.connect(self._err)

    def showEvent(self, e):
        super().showEvent(e)
        self._thread.start()

    def _err(self, err):
        QMessageBox.critical(self, "Ошибка рендера", err)
        self.reject()


# ══════════════════════════════════════════════════════════════════════════════
#  KARAOKE WINDOW  (real-time rendering, no moviepy)
# ══════════════════════════════════════════════════════════════════════════════
class KaraokeWindow(QWidget):
    """
    Полноэкранное окно карaоке.
    - Пульсирующий фон из огибающей инструментала
    - Подсветка текущего слова
    - Микрофонная дорожка внизу
    - Слайдеры громкости минуса и подсказки
    - Оценка по ритм-корреляции
    """
    closed = pyqtSignal(float)  # session score

    FONTS_TRIED = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]

    def __init__(self, data:dict, settings:dict):
        super().__init__()
        self.setWindowTitle(f"🎤  {data.get('artist','')} — {data.get('title','')}")
        self.setMinimumSize(800, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Применяем глобальный DARK_STYLE, но задаем специфичный фон самому окну
        self.setStyleSheet(DARK_STYLE + "\nKaraokeWindow { background:#08080f; }")

        self.words     = data["words"]
        self.inst_path = Path(data["instrumental"]) # Store path for fallback
        self.wpl       = settings.get("words_per_line",6)
        self.lines     = [self.words[i:i+self.wpl] for i in range(0,len(self.words),self.wpl)]

        self.audio  = AudioEngine()
        self.mic    = MicEngine()
        self.scorer = Scorer()

        if AUDIO_OK:
            self.audio.load(Path(data["vocals"]), self.inst_path)
            self.scorer.load_vocal(Path(data["vocals"]))
            self.scorer.set_words(self.words)

        self._load_env(self.inst_path)
        self.scorer.reset()

        # Mic waveform (display)
        self._mic_wave   = np.zeros(200)
        self._score_tick = 0
        self._paused     = False
        self._fallback_proc = None
        self._fallback_start_time = 0
        self._sync_offset = 0.0  # будет обновлён слайдером

        # Line-transition smoothing
        self._prev_li   = -1
        self._trans_t   = 0.0   # время начала перехода (секунды реального времени)
        self._TRANS_DUR = 0.18  # длительность fade-перехода строк (сек)

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # Возвращаем 30 FPS, чтобы не душить аудио-коллбэк
        self._timer.timeout.connect(self._tick)

    # ── envelope pre-compute ──────────────────────────────────────────────────
    def _load_env(self, path:Path, sr_env:int=100):
        self._env: Optional[np.ndarray] = None
        self._env_sr = sr_env
        self._pulse_env: Optional[np.ndarray] = None  # сглаженный удар для пульса фона
        if not AUDIO_OK: return
        try:
            data, sr = sf.read(str(path), dtype="float32")
            if data.ndim > 1: data = data.mean(1)
            hop = sr // sr_env
            env = np.array([float(np.sqrt(np.mean(data[i:i+hop]**2)))
                            for i in range(0, len(data)-hop, hop)], dtype=np.float32)
            m = env.max()
            if m > 0: env /= m
            self._env = env

            # Pulse env: более медленное сглаживание (окно ~0.4 сек) для плавной пульсации фона
            from numpy.lib.stride_tricks import sliding_window_view
            w = max(1, int(sr_env * 0.4))
            padded = np.pad(env, (w//2, w//2), mode='edge')
            smooth = np.array([padded[i:i+w].max() for i in range(len(env))], dtype=np.float32)
            sm = smooth.max()
            if sm > 0: smooth /= sm
            self._pulse_env = smooth
        except Exception as e: print(f"Env: {e}")

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(0)

        # Lyrics — will be painted in paintEvent
        lay.addStretch(1)

        # Invisible placeholder keeps layout stable
        self._lyrics_placeholder = QLabel()
        self._lyrics_placeholder.setFixedHeight(160)
        self._lyrics_placeholder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self._lyrics_placeholder)

        lay.addStretch(2)

        # Mic strip placeholder (drawn in paintEvent)
        self._mic_placeholder = QLabel()
        self._mic_placeholder.setFixedHeight(50)
        lay.addWidget(self._mic_placeholder)

        # Progress strip
        self._prog_label = QLabel()
        self._prog_label.setFixedHeight(4)
        self._prog_label.setStyleSheet("background:#1a1a2e;")
        lay.addWidget(self._prog_label)

        # Controls bar
        lay.addWidget(self._build_controls())

    def _build_controls(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(88)
        bar.setObjectName("ControlsBar") # Изолируем стили контейнера
        bar.setStyleSheet("#ControlsBar { background:rgba(8,8,20,220); border-top:1px solid #1e1e38; }")
        hl  = QHBoxLayout(bar)
        hl.setContentsMargins(18,6,18,6); hl.setSpacing(12)

        def btn(text, cb, sz=48, toggle=False):
            b = QPushButton(text); b.setFixedSize(sz,sz)
            if toggle: b.setCheckable(True)
            b.clicked.connect(cb)
            return b

        self.play_btn = btn("⏸", self._toggle_pause)
        hl.addWidget(self.play_btn)
        hl.addWidget(btn("⏹", self._stop))
        hl.addSpacing(10)

        # Instrumental volume
        vl1 = QVBoxLayout(); vl1.setSpacing(2)
        vl1.addWidget(QLabel("🎵 Минус"))
        self.sl_inst = QSlider(Qt.Orientation.Horizontal)
        self.sl_inst.setRange(0,100); self.sl_inst.setValue(100); self.sl_inst.setFixedWidth(130)
        self.sl_inst.valueChanged.connect(lambda v: setattr(self.audio,'vol_inst',v/100))
        vl1.addWidget(self.sl_inst); hl.addLayout(vl1)

        # Vocal guide volume
        vl2 = QVBoxLayout(); vl2.setSpacing(2)
        vl2.addWidget(QLabel("🎤 Подсказка"))
        self.sl_voc = QSlider(Qt.Orientation.Horizontal)
        self.sl_voc.setRange(0,100); self.sl_voc.setValue(15); self.sl_voc.setFixedWidth(130)
        self.sl_voc.valueChanged.connect(lambda v: setattr(self.audio,'vol_voc',v/100))
        vl2.addWidget(self.sl_voc); hl.addLayout(vl2)

        # Sync offset
        vl3 = QVBoxLayout(); vl3.setSpacing(2)
        vl3.addWidget(QLabel("⏱ Синхр."))
        self.sl_sync = QSlider(Qt.Orientation.Horizontal)
        self.sl_sync.setRange(-150, 150)   # -1.5s .. +1.5s  (×10ms)
        self.sl_sync.setValue(0)
        self.sl_sync.setFixedWidth(110)
        self.sl_sync.setToolTip("Сдвиг текста ±1.5 с если текст опережает/отстаёт от музыки")
        self._sync_offset = 0.0
        self.sl_sync.valueChanged.connect(lambda v: setattr(self,'_sync_offset', v/100.0))
        vl3.addWidget(self.sl_sync); hl.addLayout(vl3)

        hl.addSpacing(10)
        self.mic_btn = QPushButton("🎙 Mic")
        self.mic_btn.setCheckable(True); self.mic_btn.setFixedSize(70,46)
        self.mic_btn.toggled.connect(self._toggle_mic)
        hl.addWidget(self.mic_btn)

        # Waveform toggle
        self.wave_btn = QPushButton("〰 Фон")
        self.wave_btn.setCheckable(True); self.wave_btn.setChecked(False)
        self.wave_btn.setFixedSize(70,46)
        self.wave_btn.toggled.connect(lambda c: setattr(self,'_show_wave',c))
        self._show_wave = False
        hl.addWidget(self.wave_btn)

        hl.addStretch()

        # Score display
        score_col = QVBoxLayout(); score_col.setSpacing(0)
        self.score_lbl = QLabel("—")
        self.score_lbl.setStyleSheet("font-size:26px; font-weight:bold; color:#ffdc28;")
        self.score_sub = QLabel("")
        self.score_sub.setStyleSheet("font-size:10px; color:#888;")
        score_col.addWidget(self.score_lbl)
        score_col.addWidget(self.score_sub)
        hl.addLayout(score_col)
        hl.addWidget(QLabel("pts"))

        # Disable controls if audio is not OK
        if not AUDIO_OK:
            self.play_btn.setEnabled(False) # Pause is not supported in fallback
            self.sl_inst.setEnabled(False)
            self.sl_voc.setEnabled(False)
            self.mic_btn.setEnabled(False)
            self.score_lbl.setText("N/A")

        return bar

    # ── playback ─────────────────────────────────────────────────────────────
    def start(self):
        if AUDIO_OK:
            self.audio.play()
            self._timer.start()
        else:
            self._fallback_play()
            self._timer.start()
            QMessageBox.warning(self, "Нет звука в реальном времени",
                "Воспроизведение в реальном времени отключено, так как не найдена библиотека PortAudio.\n\n"
                "Включен резервный режим: музыка будет играть, и текст будет прокручиваться, "
                "но вы не сможете управлять громкостью или использовать микрофон.\n\n"
                "Для полного функционала установите системный пакет (например, 'portaudio-devel' на Fedora или 'libportaudio-dev' на Ubuntu), "
                "а затем перезапустите приложение.")

    def _fallback_play(self):
        try:
            self._fallback_proc = subprocess.Popen(
                ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', str(self.inst_path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._fallback_start_time = time.time()
        except FileNotFoundError:
            QMessageBox.critical(self, "Ошибка", "Не удалось запустить звук. Убедитесь, что 'ffmpeg' (и 'ffplay') установлен и доступен в PATH.")
            self._stop()

    def _toggle_pause(self):
        self._paused = not self._paused
        self.audio.pause()
        self.play_btn.setText("▶" if self._paused else "⏸")

    def _stop(self):
        if AUDIO_OK:
            self.audio.stop()
        if self._fallback_proc:
            self._fallback_proc.kill()
            self._fallback_proc = None
        self.mic.stop(); self._timer.stop()
        self.closed.emit(self.scorer.session)
        self.close()

    def closeEvent(self, e):
        # Вызывается при любом закрытии окна (крестик, Alt+F4, Escape)
        # Останавливаем всё чтобы аудио не висело в фоне
        self._timer.stop()
        if AUDIO_OK:
            self.audio.stop()
        if self._fallback_proc:
            self._fallback_proc.kill()
            self._fallback_proc = None
        self.mic.stop()
        # Emit score только если ещё не было — _stop() тоже emit'ит
        if not getattr(self, '_stopped', False):
            self._stopped = True
            self.closed.emit(self.scorer.session)
        super().closeEvent(e)

    def _stop(self):
        if getattr(self, '_stopped', False):
            return  # уже остановлено через closeEvent
        self._stopped = True
        if AUDIO_OK:
            self.audio.stop()
        if self._fallback_proc:
            self._fallback_proc.kill()
            self._fallback_proc = None
        self.mic.stop(); self._timer.stop()
        self.closed.emit(self.scorer.session)
        self.close()

    def _toggle_mic(self, on:bool):
        if on: self.mic.start(); self.mic_btn.setText("🎙 ON")
        else:  self.mic.stop();  self.mic_btn.setText("🎙 Mic")

    # ── tick (30fps) ─────────────────────────────────────────────────────────
    def _tick(self):
        if AUDIO_OK:
            pos = self.audio.position
            dur = self.audio.duration
        else:
            pos = (time.time() - self._fallback_start_time) if self._fallback_start_time > 0 else 0
            if not hasattr(self, '_fallback_dur'):
                try:
                    # This is a bit slow, should be done once
                    with sf.SoundFile(str(self.inst_path)) as f:
                        self._fallback_dur = len(f) / f.samplerate
                except:
                    self._fallback_dur = 300 # 5 minutes fallback
            dur = self._fallback_dur

        # Progress bar — redraw label width trick
        if dur > 0:
            frac = min(1.0, pos/dur)
            self._prog_label.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 #ffdc28, stop:{frac:.4f} #ffdc28,"
                f"stop:{min(frac+0.001,1):.4f} #1a1a2e, stop:1 #1a1a2e);")

        # Mic waveform
        if self.mic.active:
            self._mic_wave = self.mic.waveform()

        # Score every ~2s
        self._score_tick += 1
        if self._score_tick >= 60 and self.mic.active:
            self._score_tick = 0
            rms_win = self.mic.rms_window()
            self.scorer.score_tick(rms_win, pos)
            total = self.scorer.session
            self.score_lbl.setText(f"{total:.0f}")
            self.score_sub.setText(
                f"ритм {self.scorer.rhythm_avg:.0f}  "
                f"покр {self.scorer.coverage_avg:.0f}"
            )

        self.update()  # trigger paintEvent

        # Auto-stop
        if AUDIO_OK:
            if pos >= dur > 0 and not self.audio.is_playing:
                self._stop()
        else:
            # Check if ffplay process has exited
            if (self._fallback_proc and self._fallback_proc.poll() is not None) or (pos >= dur > 0):
                self._stop()

    # ── painting ─────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        # Apply sync offset to position used for lyrics
        pos = self.audio.position + self._sync_offset
        ctrl_h = 88
        draw_h  = H - ctrl_h - 4  # height of draw area

        # 1. Получаем текущий пульс из огибающей инструментала
        pulse = 0.0
        if self._pulse_env is not None:
            idx = max(0, min(int(self.audio.position * self._env_sr), len(self._pulse_env)-1))
            pulse = float(self._pulse_env[idx])

        # 2. Чистый тёмный фон — один цвет, никаких градиентов поверх
        bg_r = int(8  + pulse * 6)
        bg_g = int(8  + pulse * 4)
        bg_b = int(18 + pulse * 10)
        painter.fillRect(0, 0, W, H, QColor(bg_r, bg_g, bg_b))

        # 3. Виньетка по краям (только края темнее, центр чистый)
        vig = QLinearGradient(0, 0, 0, draw_h)
        vig.setColorAt(0,   QColor(0, 0, 0, 80))
        vig.setColorAt(0.2, QColor(0, 0, 0, 0))
        vig.setColorAt(0.8, QColor(0, 0, 0, 0))
        vig.setColorAt(1,   QColor(0, 0, 0, 80))
        painter.fillRect(0, 0, W, draw_h, QBrush(vig))
        # Боковая виньетка
        vig_h = QLinearGradient(0, 0, W, 0)
        vig_h.setColorAt(0,   QColor(0, 0, 0, 60))
        vig_h.setColorAt(0.15, QColor(0, 0, 0, 0))
        vig_h.setColorAt(0.85, QColor(0, 0, 0, 0))
        vig_h.setColorAt(1,   QColor(0, 0, 0, 60))
        painter.fillRect(0, 0, W, draw_h, QBrush(vig_h))

        # 4. Тонкая цветная полоска снизу — индикатор бита (не мешает тексту)
        beat_h = max(2, int(pulse * 5))
        beat_a = int(pulse * 180)
        if beat_a > 10:
            beat_grad = QLinearGradient(0, 0, W, 0)
            beat_grad.setColorAt(0,   QColor(80, 40, 200, 0))
            beat_grad.setColorAt(0.3, QColor(120, 60, 255, beat_a))
            beat_grad.setColorAt(0.5, QColor(160, 80, 255, beat_a))
            beat_grad.setColorAt(0.7, QColor(120, 60, 255, beat_a))
            beat_grad.setColorAt(1,   QColor(80, 40, 200, 0))
            painter.fillRect(0, draw_h - beat_h - 4, W, beat_h, QBrush(beat_grad))

        # 5. Опциональная осциллограмма (только если включено кнопкой)
        if self._show_wave and self._env is not None and len(self._env)>1:
            win_sec = 12.0
            c   = int(self.audio.position * self._env_sr)
            half= int(win_sec * self._env_sr / 2)
            seg = self._env[max(0,c-half):min(len(self._env),c+half)]
            if len(seg) > 1:
                mid = draw_h // 2
                amp = draw_h * 0.14
                n   = len(seg)
                def make_path(upper:bool):
                    p = QPainterPath()
                    for i,v in enumerate(seg):
                        x = W * i / n
                        y = mid + ((-1 if upper else 1) * v * amp)
                        if i==0: p.moveTo(x,y)
                        else:    p.lineTo(x,y)
                    return p
                pt = make_path(True); pb = make_path(False)
                for path in (pt, pb):
                    pen = QPen(QColor(90,130,255,28)); pen.setWidth(2)
                    painter.setPen(pen); painter.drawPath(path)

        # 4. Lyrics
        self._paint_lyrics(painter, W, draw_h, pos)

        # 5. Mic waveform strip (bottom of draw area)
        if self.mic.active and len(self._mic_wave) > 1:
            mh   = 44
            my   = draw_h - mh - 8
            n    = len(self._mic_wave)
            mid  = my + mh//2
            mx   = np.max(np.abs(self._mic_wave)) + 1e-6
            norm = self._mic_wave / mx
            path = QPainterPath()
            for i,v in enumerate(norm):
                x = W * i / n; y = mid - v * mh * 0.44
                if i==0: path.moveTo(x,y)
                else:    path.lineTo(x,y)
            pen = QPen(QColor(255,200,50,160)); pen.setWidth(2)
            painter.setPen(pen); painter.drawPath(path)

        painter.end()

    def _paint_lyrics(self, painter:QPainter, W:int, H:int, pos:float):
        if not self.lines: return

        # Find current line/word
        li, wi = 0, -1
        for l_i, line in enumerate(self.lines):
            for w_i, w in enumerate(line):
                if w["start"] <= pos:
                    li, wi = l_i, w_i

        # Track line transitions for fade effect
        now_real = time.monotonic()
        if li != self._prev_li and self._prev_li >= 0:
            self._trans_t = now_real
        self._prev_li = li

        # trans_alpha: 0.0 = just changed (old fading out/new fading in), 1.0 = stable
        elapsed = now_real - self._trans_t
        trans_alpha = min(1.0, elapsed / max(self._TRANS_DUR, 0.001))

        cy = H // 2 - 16

        def word_alpha(is_main_line: bool, opacity: float = 1.0) -> int:
            """Возвращает alpha с учётом перехода строк."""
            if is_main_line:
                # Новая активная строка: плавно появляется
                a = int(255 * min(1.0, trans_alpha * 2))
            else:
                a = int(255 * opacity)
            return max(0, min(255, a))

        def draw_line(idx:int, y:int, main:bool, opacity:float=1.0):
            if idx < 0 or idx >= len(self.lines): return
            line = self.lines[idx]

            main_font_size = 30 if main else 18
            main_font  = QFont("DejaVu Sans", main_font_size, QFont.Weight.Bold)
            adlib_font = QFont("DejaVu Sans", int(main_font_size * 0.7), QFont.Weight.Normal)

            total_w = 0
            word_parts = []
            for w in line:
                text = w["word"] + " "
                is_adlib = text.strip().startswith(('(', '['))
                font = adlib_font if is_adlib else main_font
                fm = QFontMetrics(font)
                adv = fm.horizontalAdvance(text)
                word_parts.append({
                    'text': text, 'is_adlib': is_adlib, 'font': font,
                    'adv': adv, 'start': w['start'], 'end': w['end']
                })
                total_w += adv

            x = (W - total_w) // 2
            base_alpha = word_alpha(main, opacity)

            for i, part in enumerate(word_parts):
                painter.setFont(part['font'])

                # Drop shadow
                shad = QColor(0,0,0,int(base_alpha * 0.47))
                painter.setPen(QPen(shad))
                painter.drawText(x+2, y+2, part['text'])

                if main:
                    if i < wi:
                        c = QColor(100, 100, 140, base_alpha)
                        painter.setPen(QPen(c))
                        painter.drawText(x, y, part['text'])
                    elif i == wi:
                        # Base (dim)
                        painter.setPen(QPen(QColor(140, 120, 20, base_alpha)))
                        painter.drawText(x, y, part['text'])
                        # Filled part (bright yellow)
                        pct = max(0.0, min(1.0, (pos - part['start']) / max(0.001, part['end'] - part['start'])))
                        fill_w = int(part['adv'] * pct)
                        if fill_w > 0:
                            painter.save()
                            clip_y = y - QFontMetrics(part['font']).ascent() - 5
                            clip_h = QFontMetrics(part['font']).height() + 10
                            painter.setClipRect(QRect(x, clip_y, fill_w, clip_h))
                            painter.setPen(QPen(QColor(255, 220, 40, base_alpha)))
                            painter.drawText(x, y, part['text'])
                            painter.restore()
                    else:
                        # Upcoming words: slightly pre-highlight next word
                        if i == wi + 1:
                            # Next word gets a subtle pre-glow so you can read ahead
                            time_to_next = part['start'] - pos
                            pre = max(0.0, min(1.0, 1.0 - time_to_next / 0.5))  # 0.5s lookahead
                            if pre > 0:
                                c = QColor(
                                    int(210 + pre * 45),
                                    int(210 + pre * 10),
                                    int(240 - pre * 100),
                                    base_alpha
                                )
                            else:
                                c = QColor(210, 210, 240, base_alpha)
                        else:
                            c = QColor(120,120,150,base_alpha) if part['is_adlib'] else QColor(210,210,240,base_alpha)
                        painter.setPen(QPen(c))
                        painter.drawText(x, y, part['text'])
                else:
                    color = QColor(120,120,160,base_alpha) if idx < li else (
                        QColor(170,170,170,base_alpha) if part['is_adlib'] else QColor(150,150,190,base_alpha)
                    )
                    painter.setPen(QPen(color))
                    painter.drawText(x, y, part['text'])

                x += part['adv']

        main_h = 44; sub_h = 28

        # Previous line fades out during transition
        prev_opacity = 1.0 - trans_alpha if elapsed < self._TRANS_DUR else 1.0
        draw_line(li-1, cy - sub_h - 6,  False, prev_opacity)
        draw_line(li,   cy,               True)
        draw_line(li+1, cy + main_h + 4,  False)
        draw_line(li+2, cy + main_h + sub_h + 8, False, 0.6)

    # ── keys ─────────────────────────────────────────────────────────────────
    def keyPressEvent(self, e:QKeyEvent):
        if e.key() == Qt.Key.Key_Space:  self._toggle_pause()
        elif e.key() == Qt.Key.Key_Escape: self._stop()
        elif e.key() == Qt.Key.Key_F11:
            if self.isFullScreen(): self.showNormal()
            else:                   self.showFullScreen()


# ══════════════════════════════════════════════════════════════════════════════
#  PANELS
# ══════════════════════════════════════════════════════════════════════════════
class QueuePanel(QWidget):
    play_req = pyqtSignal(int)

    def __init__(self, q:TrackQueue):
        super().__init__(); self.q = q; self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        hdr = QLabel("📋  Очередь треков")
        hdr.setStyleSheet("font-size:16px; font-weight:bold; color:#ffdc28; padding:4px 0;")
        lay.addWidget(hdr)

        self.lst = QListWidget()
        self.lst.itemDoubleClicked.connect(lambda i: self.play_req.emit(self.lst.row(i)))
        lay.addWidget(self.lst)

        row = QHBoxLayout()
        def B(t,fn): b=QPushButton(t); b.clicked.connect(fn); return b
        row.addWidget(B("➕ Файл",  self._add_file))
        row.addWidget(B("⬇️ YT",    self._download))
        row.addWidget(B("▲",        self._up))
        row.addWidget(B("▼",        self._down))
        row.addWidget(B("🗑",        self._remove))
        row.addWidget(B("🧹 Кэш",   self._clear_cache))
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        self.lst.clear()
        for i, item in enumerate(self.q.items):
            cur  = "▶" if i==self.q.current else " "
            proc = "⚡" if self.q.is_processed(item) else "  "
            self.lst.addItem(f"{cur} {proc} {item.get('artist','')} — {item.get('title','')}")

    def _add_file(self):
        paths,_ = QFileDialog.getOpenFileNames(
            self,"Добавить треки",str(Path.home()/"Music"),
            "Аудио (*.mp3 *.wav *.flac *.ogg *.m4a)")
        for p in paths:
            artist,title = self._parse_filename(p)
            self.q.add(p, artist, title)
        self.refresh()

    def _download(self):
        dlg = DownloadDialog(self); dlg.setStyleSheet(DARK_STYLE)
        dlg.track_ready.connect(self._on_dl); dlg.exec()

    def _on_dl(self, path:str):
        artist,title = self._parse_filename(path)
        self.q.add(path, artist, title); self.refresh()

    def _parse_filename(self, filename:str) -> tuple[str,str]:
        if BACKEND_OK:
            return bk.guess_meta(Path(filename).name)
        # Fallback to simple parsing if backend is not available
        stem = Path(filename).stem
        for sep in (" - "," — "," – "):
            if sep in stem:
                a,t = stem.split(sep,1); return a.strip(),t.strip()
        return "", stem

    def _up(self):
        r=self.lst.currentRow()
        if r>0: self.q.move(r,-1); self.refresh(); self.lst.setCurrentRow(r-1)

    def _down(self):
        r=self.lst.currentRow()
        if r<len(self.q.items)-1: self.q.move(r,1); self.refresh(); self.lst.setCurrentRow(r+1)

    def _remove(self):
        r=self.lst.currentRow()
        if r>=0: self.q.remove(r); self.refresh()

    def _clear_cache(self):
        r = self.lst.currentRow()
        if r < 0 or r >= len(self.q.items):
            QMessageBox.information(self, "Мимо", "Сначала выдели трек в списке.")
            return
            
        item = self.q.items[r]
        h = item.get("hash")
        title = item.get("title", "Unknown")
        
        if not h: return

        reply = QMessageBox.question(
            self, "Очистка кэша", 
            f"Сбросить кэш для трека:\n«{title}»?\n\n(Удалятся сохраненный минус, вокал и тайминги текста. При следующем запуске трек обработается заново)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            deleted = 0
            # Ищем и удаляем 3 главных файла, которые генерит бэкенд
            for ext in ["_vocals.wav", "_instrumental.wav", "_timings.json"]:
                p = APP_DIR / f"{h}{ext}"
                if p.exists():
                    try:
                        p.unlink()
                        deleted += 1
                    except Exception as e:
                        print(f"Ошибка удаления {p}: {e}")
            
            if deleted > 0:
                QMessageBox.information(self, "Готово", f"Очищено кэш-файлов: {deleted}\nИконка молнии (⚡) у трека пропадет.")
            else:
                QMessageBox.information(self, "Пусто", "Для этого трека кэш еще не создавался.")
            
            self.refresh() # Обновляем список, чтобы молния ⚡ убралась


class LeaderboardPanel(QWidget):
    def __init__(self, lb:Leaderboard):
        super().__init__(); self.lb=lb; self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        hdr = QLabel("🏆  Лидерборд")
        hdr.setStyleSheet("font-size:16px; font-weight:bold; color:#ffdc28; padding:4px 0;")
        lay.addWidget(hdr)
        self.lst = QListWidget()
        self.lst.setStyleSheet("font-family:monospace; font-size:13px;")
        lay.addWidget(self.lst)
        lay.addWidget(self._btn("🔄 Обновить", self.refresh))
        self.refresh()

    def _btn(self,t,fn): b=QPushButton(t); b.clicked.connect(fn); return b

    def refresh(self):
        self.lst.clear()
        medals=["🥇","🥈","🥉"]
        for i,s in enumerate(self.lb.all_scores()[:50]):
            m = medals[i] if i<3 else f"   {i+1}."
            self.lst.addItem(
                f"{m}  {s['player']:<14}  {s['score']:>5.1f} pts  "
                f"{s['track'][:28]}  {s['date']}")


class SettingsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.s = load_settings()
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("⚙️  Настройки"))

        g1 = QGroupBox("Распознавание речи")
        g1l = QVBoxLayout(g1)
        self._row(g1l,"Whisper модель:","model_cb",
                  ["tiny","base","small","medium","large","large-v3"],
                  self.s.get("model","medium"),
                  lambda t: self.s.update({"model":t}))
        self._row(g1l,"Язык:","lang_cb",["ru","en","auto"],
                  self.s.get("lang","ru"),
                  lambda t: self.s.update({"lang":t}))
        lay.addWidget(g1)

        g2 = QGroupBox("Дисплей")
        g2l = QVBoxLayout(g2)
        self._row(g2l,"Слов в строке:","wpl_cb",["4","5","6","7","8"],
                  str(self.s.get("words_per_line",6)),
                  lambda t: self.s.update({"words_per_line":int(t)}))
        lay.addWidget(g2)

        g3 = QGroupBox("Профиль")
        g3l = QVBoxLayout(g3)
        rl = QHBoxLayout(); rl.addWidget(QLabel("Имя:"))
        self.name_edit = QLineEdit(self.s.get("player_name","Player 1"))
        self.name_edit.textChanged.connect(lambda t: self.s.update({"player_name":t}))
        rl.addWidget(self.name_edit); g3l.addLayout(rl)
        lay.addWidget(g3)

        if BACKEND_OK:
            g4 = QGroupBox("Железо")
            g4l = QVBoxLayout(g4)
            g4l.addWidget(QLabel(bk.gpu().info()))
            lay.addWidget(g4)

        save_btn = QPushButton("💾  Сохранить")
        save_btn.clicked.connect(lambda: save_settings(self.s))
        lay.addWidget(save_btn)
        lay.addStretch()

    def _row(self, lay, label, attr, items, current, cb):
        hl = QHBoxLayout(); hl.addWidget(QLabel(label))
        cb_w = QComboBox(); cb_w.addItems(items); cb_w.setCurrentText(current)
        cb_w.currentTextChanged.connect(cb)
        setattr(self, attr, cb_w); hl.addWidget(cb_w); lay.addLayout(hl)


# ══════════════════════════════════════════════════════════════════════════════
#  VOICE COMMAND WIDGET
# ══════════════════════════════════════════════════════════════════════════════
class VoiceWidget(QWidget):
    command = pyqtSignal(str)

    def __init__(self):
        super().__init__(); self._t=None; self._build()

    def _build(self):
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        self.btn = QPushButton("🎙 Голос")
        self.btn.setFixedHeight(36)
        self.btn.setToolTip(
            "Нажми и скажи:\n"
            "«следующий трек [название]» — добавить/найти в очереди\n"
            "«напеть» — поёшь 5 сек, ищем по слуху\n"
            "«стоп» — пауза")
        self.btn.clicked.connect(self._record)
        self.lbl = QLabel("")
        self.lbl.setStyleSheet("color:#888; font-size:11px;")
        lay.addWidget(self.btn); lay.addWidget(self.lbl)

    def _record(self):
        self.btn.setEnabled(False)
        self.lbl.setText("⏺ Запись…")
        self._t = VoiceThread(5.0)
        self._t.recognized.connect(self._on_rec)
        self._t.finished.connect(lambda: self.btn.setEnabled(True))
        self._t.start()

    def _on_rec(self, text:str):
        self.lbl.setText(text[:60])
        if not any(text.startswith(c) for c in ("❌","⏺","🤔")):
            self.command.emit(text)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎤  Rap Karaoke")
        self.setMinimumSize(1020, 680)
        self.queue = TrackQueue()
        self.lb    = Leaderboard()
        self._karaoke: Optional[KaraokeWindow] = None
        self._build()
        self.setStyleSheet(DARK_STYLE)
        self._update_status()

    # ── build ─────────────────────────────────────────────────────────────────
    def _build(self):
        cw = QWidget(); self.setCentralWidget(cw)
        lay = QVBoxLayout(cw); lay.setContentsMargins(12,12,12,8)

        # Top bar
        top = QHBoxLayout()
        title = QLabel("🎤  RAP KARAOKE")
        title.setStyleSheet("font-size:22px; font-weight:bold; color:#ffdc28; letter-spacing:3px;")
        top.addWidget(title)
        top.addStretch()

        self.voice = VoiceWidget()
        self.voice.command.connect(self._handle_voice)
        top.addWidget(self.voice)

        play_btn = QPushButton("▶  Запустить")
        play_btn.setFixedHeight(36)
        play_btn.clicked.connect(self._play_current)
        top.addWidget(play_btn)
        lay.addLayout(top)

        # Tabs
        tabs = QTabWidget()

        # Queue
        qw = QWidget(); ql = QVBoxLayout(qw); ql.setContentsMargins(0,8,0,0)
        self.queue_panel = QueuePanel(self.queue)
        self.queue_panel.play_req.connect(self._play_idx)
        ql.addWidget(self.queue_panel)
        tabs.addTab(qw, "📋 Очередь")

        # Leaderboard
        self.lb_panel = LeaderboardPanel(self.lb)
        tabs.addTab(self.lb_panel, "🏆 Лидерборд")

        # Settings
        self.settings_panel = SettingsPanel()
        tabs.addTab(self.settings_panel, "⚙️ Настройки")

        lay.addWidget(tabs)

        self.setStatusBar(QStatusBar())

    def _update_status(self):
        if BACKEND_OK: msg = bk.gpu().info()
        else:          msg = "⚠️  rap_karaoke.py не найден — обработка недоступна"
        self.statusBar().showMessage(msg)

    def _play_current(self):
        self._play_idx(self.queue.current)

    def _play_idx(self, idx:int):
        if idx < 0 or idx >= len(self.queue.items):
            QMessageBox.information(self, "Очередь пуста",
                                    "Добавь треки через «➕ Файл» или «⬇️ YT»!")
            return
        self.queue.current = idx
        item = self.queue.items[idx]
        self.queue_panel.refresh()

        data = self._get_processed_data(item)
        if data:
            self._open_karaoke(data)

    def _get_processed_data(self, item: dict) -> Optional[dict]:
        data = None
        
        # 1. Если трек уже обработан (есть тайминги), грузим из кэша
        if self.queue.is_processed(item):
            h = item["hash"]
            words = json.load(open(APP_DIR/f"{h}_timings.json", encoding="utf-8"))
            data = {
                "vocals":       str(APP_DIR/f"{h}_vocals.wav"),
                "instrumental": str(APP_DIR/f"{h}_instrumental.wav"),
                "words":        words, "candidates":[], "file_hash":h,
                "artist":item.get("artist",""), "title":item.get("title",""),
            }
        # 2. Иначе — запускаем полный процесс
        else:
            if not BACKEND_OK:
                QMessageBox.warning(self,"Нет бэкенда", "rap_karaoke.py не найден."); return None

            dlg = ProcessingDialog(item, self.settings_panel.s, self)
            dlg.setStyleSheet(DARK_STYLE)
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result_data:
                return None
            data = dlg.result_data

            if data.get("candidates"):
                confirm = LyricsConfirmDialog(data["candidates"], data["artist"], data["title"], self)
                confirm.setStyleSheet(DARK_STYLE)
                if confirm.exec() == QDialog.DialogCode.Accepted and confirm.selected:
                    sel = confirm.selected
                    if sel.get("words"):
                        data["words"] = sel["words"]
                        h = data["file_hash"]
                        with open(APP_DIR/f"{h}_timings.json","w",encoding="utf-8") as f:
                            json.dump(data["words"],f,ensure_ascii=False)

        # 3. АВТОМАТИЧЕСКИЙ РЕНДЕР ВИДЕО
        if data and data.get("words"):
            artist = data.get("artist", "")
            title = data.get("title", Path(item['path']).stem)
            safe_filename = re.sub(r'[\\/*?:"<>|]', "", f"{artist} - {title}" if artist else title) + "_karaoke.mp4"
            save_path = KARAOKE_VIDEOS_DIR / safe_filename

            # Если файла видео еще нет — рендерим
            if not save_path.exists():
                wpl = self.settings_panel.s.get("words_per_line", 6)
                rd = RenderDialog(data, wpl, save_path, self)
                rd.setStyleSheet(DARK_STYLE)
                rd.exec()

        self.queue_panel.refresh()
        return data

    def _open_karaoke(self, data:dict):
        if self._karaoke:
            self._karaoke.close(); self._karaoke = None
        win = KaraokeWindow(data, self.settings_panel.s)
        win.closed.connect(lambda score: self._on_karaoke_closed(
            data["file_hash"],
            f"{data.get('artist','')} — {data.get('title','')}",
            score))
        self._karaoke = win
        win.showMaximized()
        win.start()

    def _on_karaoke_closed(self, h:str, name:str, score:float):
        if score >= 1.0:
            player = self.settings_panel.s.get("player_name","Player")
            self.lb.add(h, name, player, score)
            self.lb_panel.refresh()
        self._karaoke = None

    # ── voice commands ─────────────────────────────────────────────────────────
    def _handle_voice(self, text:str):
        low = text.lower()
        triggers_next  = any(k in low for k in ["следующий трек","следующий","next трек"])
        triggers_add   = any(k in low for k in ["добавить","добавь","поставить"])
        triggers_hum   = any(k in low for k in ["напеть","напой","насвисти"])
        triggers_stop  = any(k in low for k in ["стоп","пауза","stop","pause"])

        if triggers_stop and self._karaoke:
            self._karaoke._toggle_pause(); return

        if triggers_hum:
            self._hum_search(); return

        query = ""
        for kw in ["следующий трек","следующий","добавить","добавь","поставить","next"]:
            if kw in low:
                query = text[low.find(kw)+len(kw):].strip(); break

        if not query: query = text.strip()

        if query:
            # 1. Ищем в очереди
            match = self._fuzzy_queue(query)
            if match is not None:
                self.statusBar().showMessage(f"🎵 Ставим: {self.queue.items[match]['title']}")
                self._play_idx(match); return
            # 2. Качаем
            self.statusBar().showMessage(f"⬇️ Качаем: {query}…")
            self._auto_dl(query)
        else:
            self.statusBar().showMessage(f"🎙 Не понял: «{text[:60]}»")

    def _fuzzy_queue(self, q:str) -> Optional[int]:
        q_words = set(q.lower().split())
        best, bi = 0, None
        for i,item in enumerate(self.queue.items):
            t = f"{item.get('artist','')} {item.get('title','')}".lower()
            score = len(q_words & set(t.split()))
            if score > best: best,bi = score,i
        return bi if best >= max(1,len(q_words)//2) else None

    def _auto_dl(self, query:str):
        self._dl_thread = DownloadThread(query, str(DOWNLOADS_DIR), is_url=False)
        self._dl_thread.progress.connect(self.statusBar().showMessage)
        self._dl_thread.finished.connect(self._on_auto_dl)
        self._dl_thread.error.connect(lambda e: self.statusBar().showMessage(f"❌ {e[:80]}"))
        self._dl_thread.start()

    def _on_auto_dl(self, path:str):
        if not BACKEND_OK:
            self.statusBar().showMessage("❌ Ошибка: бэкенд не найден для парсинга имени.", 5000)
            return
        artist, title = bk.guess_meta(Path(path).name)
        self.queue.add(path, artist, title)
        self.queue_panel.refresh()
        self.statusBar().showMessage(f"✅ Скачано: {title}")

    def _hum_search(self):
        self.statusBar().showMessage("🎵 Напой мелодию (5 сек)…")
        self._hum_thread = VoiceThread(5.0)
        self._hum_thread.recognized.connect(self._on_hum)
        self._hum_thread.start()

    def _on_hum(self, text:str):
        clean = re.sub(r"[^а-яёa-z0-9\s]","",text.lower()).strip()
        if clean and not clean.startswith("❌"):
            self.statusBar().showMessage(f"🔍 Ищем по напевке: {clean}…")
            self._auto_dl(clean)
        else:
            self.statusBar().showMessage("🤔 Напевка не распознана, попробуй текстом")

    # ── close ─────────────────────────────────────────────────────────────────
    def closeEvent(self, e):
        save_settings(self.settings_panel.s)
        self.queue.save()
        if self._karaoke: self._karaoke.audio.stop(); self._karaoke.close()
        super().closeEvent(e)


# ══════════════════════════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Rap Karaoke")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()