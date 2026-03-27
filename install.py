#!/usr/bin/env python3
"""
Rap Karaoke — Smart Installer
==============================
Определяет железо (NVIDIA / AMD / CPU) и устанавливает
правильную версию torch + все зависимости.

Запуск:
    python install.py
"""

import sys, subprocess, shutil, platform, os
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
#  GPU DETECTION
# ══════════════════════════════════════════════════════════════════════════════
def detect() -> tuple[str, str]:
    """Возвращает (backend, human_name): 'nvidia'|'amd'|'cpu'"""

    # ── NVIDIA ────────────────────────────────────────────────────────────────
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(
                ["nvidia-smi","--query-gpu=name,driver_version","--format=csv,noheader"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                lines = r.stdout.strip().splitlines()
                name  = lines[0].split(",")[0].strip()
                return "nvidia", f"NVIDIA {name}"
        except Exception as e:
            print(f"  nvidia-smi error: {e}")

    # ── AMD ROCm ──────────────────────────────────────────────────────────────
    rocm_smi  = shutil.which("rocm-smi")
    kfd_nodes = Path("/sys/class/kfd/kfd/topology/nodes")
    amd_found = kfd_nodes.exists()

    if rocm_smi:
        try:
            r = subprocess.run(["rocm-smi","--showproductname"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                amd_found = True
                for line in r.stdout.splitlines():
                    if "GPU" in line.upper() or "Radeon" in line:
                        name = line.strip().split(":")[-1].strip()
                        return "amd", f"AMD {name} (ROCm)"
        except: pass

    if amd_found:
        return "amd", "AMD GPU (ROCm)"

    # ── Apple Silicon ─────────────────────────────────────────────────────────
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mps", f"Apple Silicon ({platform.processor()})"

    # ── CPU ───────────────────────────────────────────────────────────────────
    import multiprocessing
    cores = multiprocessing.cpu_count()
    return "cpu", f"CPU ({platform.processor() or 'unknown'}, {cores} ядер)"


# ══════════════════════════════════════════════════════════════════════════════
#  TORCH INDEX URLS
# ══════════════════════════════════════════════════════════════════════════════
TORCH_URLS = {
    "nvidia": "https://download.pytorch.org/whl/cu121",   # CUDA 12.1
    "amd":    "https://download.pytorch.org/whl/rocm6.0", # ROCm 6.0
    "mps":    None,                                        # pip default (macOS)
    "cpu":    "https://download.pytorch.org/whl/cpu",
}

# audio-separator: ONNX Runtime с GPU ускорением
AUDIO_SEP = {
    "nvidia": "audio-separator[gpu]",  # ONNX Runtime + CUDA
    "amd":    "audio-separator[cpu]",  # ROCm через ONNX пока нестабилен
    "mps":    "audio-separator[cpu]",
    "cpu":    "audio-separator[cpu]",
}


# ══════════════════════════════════════════════════════════════════════════════
#  PACKAGES
# ══════════════════════════════════════════════════════════════════════════════
CORE = [
    # Обработка аудио
    "demucs",
    "openai-whisper",
    "whisperx",
    # Видео (legacy build_video)
    "moviepy==1.0.3",
    # Изображения
    "Pillow",
    "numpy",
    # Сеть + скрейпинг
    "requests",
    "beautifulsoup4",
    "yt-dlp",
    # Фонетика
    "jellyfish",
    # GUI
    "PyQt6",
    # Аудио RT
    "sounddevice",
    "soundfile",
    # Анализ
    "librosa",
]


def pip(*args, **kwargs):
    subprocess.run([sys.executable, "-m", "pip", "install", *args], check=True, **kwargs)


def pip_index(url:str, *packages):
    subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--index-url", url, *packages],
        check=True)


# ══════════════════════════════════════════════════════════════════════════════
#  ROCM SYSTEM PACKAGES HINT
# ══════════════════════════════════════════════════════════════════════════════
ROCM_HINT = """
──────────────────────────────────────────────────────────────
  AMD ROCm — системные пакеты (если ещё не установлены):

  Arch Linux:
    sudo pacman -S rocm-opencl-runtime hip-runtime-amd

  Ubuntu 22.04 / 24.04:
    sudo apt install rocm-dev

  Подробная инструкция:
    https://rocm.docs.amd.com/en/latest/deploy/linux/index.html
──────────────────────────────────────────────────────────────
"""

CUDA_VERSIONS = {
    "cu121": "CUDA 12.1 (GTX 16xx / RTX 20xx-40xx)",
    "cu118": "CUDA 11.8 (GTX 10xx / старые RTX)",
}


# ══════════════════════════════════════════════════════════════════════════════
ROCM_PYTHON_HINT = """
╔══════════════════════════════════════════════════════════════╗
║  AMD ROCm — важные замечания                                  ║
╠══════════════════════════════════════════════════════════════╣
║  torch для ROCm собран только под Python 3.10 / 3.11.        ║
║  Если у тебя Python 3.12+ — скрипт может упасть на pip.      ║
║                                                              ║
║  Arch Linux: python310 / python311 из AUR                    ║
║    yay -S python310                                          ║
║    python3.10 -m venv .venv && source .venv/bin/activate     ║
║    python3.10 install.py                                     ║
║                                                              ║
║  Ubuntu 22.04 / 24.04 (deadsnakes PPA):                     ║
║    sudo add-apt-repository ppa:deadsnakes/ppa                ║
║    sudo apt install python3.11 python3.11-venv               ║
║    python3.11 -m venv .venv && source .venv/bin/activate     ║
║    python3.11 install.py                                     ║
║                                                              ║
║  ROCm системные пакеты (если ещё не установлены):            ║
║    Arch:   sudo pacman -S rocm-opencl-runtime hip-runtime-amd ║
║    Ubuntu: sudo apt install rocm-dev                         ║
║    Docs:   https://rocm.docs.amd.com/                        ║
╚══════════════════════════════════════════════════════════════╝
"""


def main():
    print("=" * 60)
    print("  🎤  Rap Karaoke — Smart Installer")
    print("=" * 60)

    backend, hw_name = detect()
    icons = {"nvidia":"🟢","amd":"🔴","mps":"🍎","cpu":"⚪"}
    print(f"\n{icons.get(backend,'?')} Железо: {hw_name}")
    print(f"   Backend: {backend.upper()}")
    print(f"   Python:  {sys.version.split()[0]}")

    # ── AMD: предупреждение про Python версию ────────────────────────────────
    if backend == "amd":
        major, minor = sys.version_info.major, sys.version_info.minor
        if minor >= 12:
            print(f"\n⚠️  ВНИМАНИЕ: у тебя Python {major}.{minor}.")
            print("   PyTorch для ROCm поддерживает только Python 3.10 и 3.11.")
            print("   Рекомендуется создать окружение на 3.10 или 3.11 (см. подсказку ниже).")
            print(ROCM_PYTHON_HINT)
            go = input("   Продолжить всё равно? (y/n) [n]: ").strip().lower()
            if go != "y":
                print("   Прерываем. Создай окружение на Python 3.10/3.11 и запусти снова.")
                sys.exit(0)
        else:
            print(ROCM_PYTHON_HINT)

    # ── Системные зависимости ─────────────────────────────────────────────────
    print("\n⚠️  Системные зависимости (убедись, что установлены):")
    print("   Arch:   sudo pacman -S ffmpeg portaudio")
    print("   Fedora: sudo dnf install ffmpeg portaudio-devel")
    print("   Ubuntu: sudo apt install ffmpeg libportaudio2 libportaudio-dev")
    print("\n   PortAudio нужен для sounddevice (GUI-звук).")
    print("   ffmpeg нужен для moviepy и воспроизведения аудио.")
    input("\n   Нажми Enter, чтобы продолжить установку Python-пакетов…")

    # ── CUDA версия для NVIDIA ────────────────────────────────────────────────
    torch_url = TORCH_URLS[backend]
    if backend == "nvidia":
        print("\n  Какая версия CUDA? (см. nvidia-smi, строка CUDA Version)")
        print("  1) CUDA 12.x  (RTX 20xx, 30xx, 40xx — большинство карт)")
        print("  2) CUDA 11.8  (GTX 10xx, 16xx, RTX 20xx со старым драйвером)")
        choice = input("  Введи 1 или 2 [по умолчанию 1]: ").strip()
        if choice == "2":
            torch_url = "https://download.pytorch.org/whl/cu118"
            print("  → CUDA 11.8")
        else:
            print("  → CUDA 12.1")

    # ── Установка torch ───────────────────────────────────────────────────────
    print("\n📦 Устанавливаем torch + torchaudio…")
    if torch_url:
        pip_index(torch_url, "torch", "torchaudio")
    else:
        pip("torch", "torchaudio")

    # ── Основные пакеты ───────────────────────────────────────────────────────
    print("\n📦 Устанавливаем зависимости…")
    audio_sep = AUDIO_SEP[backend]
    pip(*CORE, audio_sep)

    # ── Проверка torch ────────────────────────────────────────────────────────
    print("\n🔍 Проверяем torch…")
    check = (
        "import torch; "
        "cuda = torch.cuda.is_available(); "
        "name = torch.cuda.get_device_name(0) if cuda else 'нет GPU'; "
        "print(f'  CUDA: {cuda}  |  Устройство: {name}  |  torch {torch.__version__}')"
    )
    try:
        r = subprocess.run([sys.executable, "-c", check], capture_output=True, text=True)
        print(r.stdout.strip() or ("  " + r.stderr.strip()[:200]))
    except: pass

    print("\n✅  Установка завершена!")
    print("   Запуск: python rap_karaoke_app.py")

    if backend == "amd":
        print("\n💡 Если torch не видит GPU:")
        print("   1. Проверь: rocm-smi — должны быть карты в списке")
        print("   2. Добавь пользователя в группу: sudo usermod -aG video,render $USER")
        print("   3. Перелогинься или выполни: newgrp render")


if __name__ == "__main__":
    main()