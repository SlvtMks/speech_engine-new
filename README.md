## Офлайн STT ⇄ TTS движок

Полностью офлайн-движок распознавания и синтеза речи на Python:

- **STT** (Speech-to-Text) на базе `faster-whisper` (MIT)
- **TTS** (Text-to-Speech):
  - Русский: **Silero TTS** (MIT)
  - Английский: **Coqui TTS** (MPL-2.0)
- Поддержка **русского** и **английского** языков
- **CLI-интерфейс** с командами для STT, TTS и режима "chat"
- Работа на **CPU и GPU** (автоопределение)
- **Автоопределение языка** для STT
- **Нормализация аудио**, приведение к `wav 16 kHz mono pcm_s16le`
- **Таймкоды сегментов** в результатах STT
- **Поддержка нескольких голосов** в одном аудио (для русского TTS)
- **Офлайн работа** после первичного скачивания моделей

---

## Установка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

---

## Запуск API (FastAPI)

Проект содержит HTTP API (см. `speech_engine/api.py`).

### Локально

```bash
uvicorn speech_engine.api:app --host 0.0.0.0 --port 8000
```

Проверка:

```bash
curl http://localhost:8000/health
```

---

## Запуск Web UI (Next.js)

Фронтенд находится в директории `web/`.

```bash
cd web
npm ci
npm run dev
```

По умолчанию фронт ожидает API по базовому URL (см. `NEXT_PUBLIC_API_BASE_URL` в Docker/Compose ниже).

---

## Запуск через Docker Compose (backend + web)

Самый простой способ поднять всё вместе:

```bash
docker compose up --build
```

- Backend: `http://localhost:8000`
- Web: `http://localhost:3000`

---

## Тесты

Тесты находятся в `tests/` и используют стандартный `unittest`.

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### 2. Установка ffmpeg (обязательно для pydub)

**Windows:**
- Скачайте сборку с [официального сайта ffmpeg](https://ffmpeg.org/download.html)
- Добавьте `ffmpeg/bin` в переменную окружения `PATH`

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install -y ffmpeg
```

**Linux (Arch):**
```bash
sudo pacman -S ffmpeg
```

Проверьте установку:
```bash
ffmpeg -version
```

---

## Первое использование

При первом запуске STT или TTS:

- `faster-whisper` автоматически скачает модель (по умолчанию `large-v3`)
- Silero TTS скачает модель для русского языка через `torch.hub`
- Coqui TTS скачает модель для английского языка (`tts_models/en/ljspeech/tacotron2-DDC`)

После первичного скачивания модели хранятся локально, и дальнейшая работа идёт **полностью офлайн** (без доступа в интернет).

---

## Использование CLI

### STT — распознавание речи

```bash
python -m speech_engine.cli stt input.wav --lang auto
```

**Параметры:**
- `input.wav` — путь к входному аудиофайлу
- `--lang`:
  - `ru` — принудительно русский
  - `en` — принудительно английский
  - `auto` — автоопределение языка (**по умолчанию**)

**Вывод:**
- Полный распознанный текст
- Определённый язык
- Список сегментов с таймкодами

**Пример:**
```bash
python -m speech_engine.cli stt recording.wav --lang auto
```

### TTS — синтез речи из текста

**Базовое использование:**
```bash
python -m speech_engine.cli tts "Привет мир" --lang ru --out out.wav
```

**Параметры:**
- `"Привет мир"` — текст для озвучки
- `--lang` — язык синтеза (`ru` или `en`)
- `--out` — путь к выходному WAV-файлу
- `--speaker` (опционально, только для `ru`) — выбор голоса:
  - `aidar` (мужской, по умолчанию)
  - `baya` (женский)
  - `kseniya` (женский)
  - `xenia` (женский)
  - `eugene` (мужской)
  - `random` (случайный)

**Примеры:**
```bash
# Русский с голосом по умолчанию
python -m speech_engine.cli tts "Привет, это тест" --lang ru --out ru_test.wav

# Русский с женским голосом
python -m speech_engine.cli tts "Привет, это тест" --lang ru --out ru_baya.wav --speaker baya

# Английский
python -m speech_engine.cli tts "Hello world" --lang en --out en_test.wav
```

### Множественные голоса в одном аудио (только для русского)

Используйте маркеры `[speaker]текст[/speaker]` для указания разных голосов:

```bash
python -m speech_engine.cli tts "[aidar]Привет, меня зовут Иван.[/aidar] [baya]А меня зовут Мария.[/baya]" --lang ru --out dialog.wav
```

Или с переходами между голосами:
```bash
python -m speech_engine.cli tts "[aidar]Первая реплика.[kseniya]Вторая реплика.[eugene]Третья реплика." --lang ru --out multi_voice.wav
```

### CHAT — режим STT → TTS

Распознаёт речь и озвучивает её обратно:

```bash
python -m speech_engine.cli chat input.wav --out reply.wav
```

**Поведение:**
1. Распознаёт речь из `input.wav` через STT
2. Определяет язык исходного аудио
3. Синтезирует **тот же текст** в `reply.wav` с помощью TTS
4. Язык синтеза выбирается на основе результата STT (`ru` или `en`)

---

## Структура проекта

```
speech-engine/
├── LICENSE                 # MIT лицензия для прикладного кода
├── README.md              # Документация
├── requirements.txt       # Зависимости Python
├── LICENSES.md            # Полный перечень лицензий зависимостей
└── speech_engine/
    ├── __init__.py        # Инициализация модуля
    ├── audio.py           # Обработка и нормализация аудио
    ├── stt.py             # Speech-to-Text (faster-whisper)
    ├── tts.py             # Text-to-Speech (Silero + Coqui)
    └── cli.py             # CLI интерфейс
```

---

## Технические детали

### STT (speech_engine/stt.py)

- **Библиотека:** `faster-whisper` (MIT)
- **Модель:** `Systran/faster-whisper-large-v3` с HuggingFace
- **Особенности:**
  - Автоопределение устройства (CPU/GPU)
  - Тип вычислений: `float16` на GPU, `int8` на CPU
  - VAD-фильтрация включена
  - Параметры: `beam_size=5`, `temperature=0.0`
  - Возврат сегментов с таймкодами

### TTS (speech_engine/tts.py)

**Русский язык:**
- **Библиотека:** Silero TTS через `torch.hub` (MIT)
- **Модель:** `snakers4/silero-models` (silero_tts, language="ru")
- **Голоса:** aidar, baya, kseniya, xenia, eugene, random
- **Особенности:**
  - Поддержка нескольких голосов в одном аудио через маркеры
  - Автоматическое разбиение длинных текстов (>900 символов)

**Английский язык:**
- **Библиотека:** Coqui TTS (MPL-2.0)
- **Модель:** `tts_models/en/ljspeech/tacotron2-DDC` (Apache 2.0)

### Обработка аудио (speech_engine/audio.py)

Функция `preprocess_audio()`:
- Принимает аудио в любом поддерживаемом формате
- Приводит к: `wav`, `16 kHz`, `mono`, `pcm_s16le`
- Добавляет 1 секунду тишины в начало
- Выполняет нормализацию громкости

---

## Лицензии

### Прикладной код

Весь код в директории `speech_engine/` (кроме зависимостей) написан с нуля и распространяется под **MIT лицензией** (см. файл `LICENSE`).

### Зависимости

Полный перечень лицензий всех зависимостей и моделей см. в файле **`LICENSES.md`**.

**Краткий список:**
- `faster-whisper` — MIT
- `coqui-tts` — MPL-2.0
- `torch` / `torchaudio` — BSD-style
- `pydub` — MIT
- `soundfile` — BSD-3-Clause
- `numpy` — BSD-3-Clause
- `transformers` — Apache 2.0
- `omegaconf` — BSD-3-Clause

**Модели:**
- STT: `Systran/faster-whisper-large-v3` — открытая модель с HuggingFace
- TTS (RU): Silero TTS — MIT
- TTS (EN): `tts_models/en/ljspeech/tacotron2-DDC` — Apache 2.0

---

## Офлайн-режим

- Интернет требуется **только при первом запуске** для скачивания моделей
- После загрузки моделей весь пайплайн работает **полностью офлайн**
- Не используются облачные API
- Не применяются проприетарные модели

---

## Примеры использования

### Тестовый сценарий

1. **STT (русский):**
```bash
python -m speech_engine.cli stt test_ru.wav --lang auto
```

2. **TTS (английский):**
```bash
python -m speech_engine.cli tts "Hello world, this is a test" --lang en --out en.wav
```

3. **TTS (русский с разными голосами):**
```bash
python -m speech_engine.cli tts "[aidar]Привет.[baya]Как дела?[/baya]" --lang ru --out dialog.wav
```

4. **CHAT (STT → TTS):**
```bash
python -m speech_engine.cli chat test_ru.wav --out reply.wav
```

---

## Поддержка

При возникновении проблем:
1. Убедитесь, что установлен `ffmpeg` и доступен в `PATH`
2. Проверьте, что все зависимости установлены: `pip install -r requirements.txt`
3. При первом запуске убедитесь в наличии интернет-соединения для скачивания моделей
