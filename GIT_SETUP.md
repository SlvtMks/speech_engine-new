# Пошаговая инструкция: Загрузка проекта на GitHub

## Шаг 1: Создание репозитория на GitHub

1. Откройте https://github.com и войдите в аккаунт
2. Нажмите кнопку **"+"** в правом верхнем углу → выберите **"New repository"**
3. Заполните форму:
   - **Repository name:** `speech-engine` (или другое имя)
   - **Description:** "Офлайн STT ⇄ TTS движок для русского и английского языков"
   - Выберите **Public** или **Private**
   - **НЕ ставьте галочки** на:
     - ❌ Add a README file
     - ❌ Add .gitignore  
     - ❌ Choose a license
     (у нас уже есть эти файлы)
4. Нажмите **"Create repository"**

После создания GitHub покажет страницу с инструкциями. **Скопируйте URL репозитория** (он будет выглядеть как `https://github.com/ваш-username/speech-engine.git`)

---

## Шаг 2: Инициализация Git в проекте

Откройте терминал (PowerShell или CMD) в папке проекта `F:\speech-engine`:

### Проверка, установлен ли Git:

```bash
git --version
```

Если Git не установлен:
- Скачайте с https://git-scm.com/download/win
- Установите с настройками по умолчанию
- Перезапустите терминал

### Инициализация репозитория:

```bash
# Перейдите в папку проекта (если еще не там)
cd F:\speech-engine

# Инициализируйте Git-репозиторий
git init

# Добавьте все файлы
git add .

# Создайте первый коммит
git commit -m "Initial commit: Speech Engine STT/TTS"
```

---

## Шаг 3: Подключение к GitHub

Замените `<URL>` на реальный URL вашего репозитория (который вы скопировали на шаге 1):

```bash
# Добавьте удалённый репозиторий
git remote add origin https://github.com/ваш-username/speech-engine.git

# Проверьте, что всё правильно
git remote -v
```

Должно показать:
```
origin  https://github.com/ваш-username/speech-engine.git (fetch)
origin  https://github.com/ваш-username/speech-engine.git (push)
```

---

## Шаг 4: Загрузка кода на GitHub

```bash
# Переименуйте ветку в main (если нужно)
git branch -M main

# Загрузите код на GitHub
git push -u origin main
```

При первом `push` GitHub попросит авторизацию:
- **Вариант 1:** Введите логин и пароль GitHub (или Personal Access Token)
- **Вариант 2:** Используйте GitHub Desktop (графический интерфейс)

---

## Альтернатива: GitHub Desktop (проще для новичков)

Если командная строка кажется сложной:

1. Скачайте **GitHub Desktop**: https://desktop.github.com/
2. Установите и войдите в аккаунт GitHub
3. В GitHub Desktop:
   - File → Add Local Repository
   - Выберите папку `F:\speech-engine`
   - Нажмите "Publish repository"
   - Выберите имя и создайте репозиторий

---

## Проверка результата

После успешной загрузки:

1. Откройте ваш репозиторий на GitHub: `https://github.com/ваш-username/speech-engine`
2. Убедитесь, что все файлы загружены:
   - ✅ `speech_engine/` (папка с кодом)
   - ✅ `README.md`
   - ✅ `LICENSES.md`
   - ✅ `LICENSE`
   - ✅ `requirements.txt`

---

## Что делать дальше

### Для передачи заказчику:

1. **Если репозиторий Public:**
   - Просто передайте ссылку: `https://github.com/ваш-username/speech-engine`

2. **Если репозиторий Private:**
   - Добавьте заказчика как collaborator:
     - Settings → Collaborators → Add people
     - Введите email заказчика
   - Или передайте ссылку и дайте доступ

### Заказчик сможет клонировать:

```bash
git clone https://github.com/ваш-username/speech-engine.git
cd speech-engine
pip install -r requirements.txt
```

---

## Решение проблем

### Ошибка "remote origin already exists"

```bash
# Удалите старый remote
git remote remove origin

# Добавьте заново
git remote add origin https://github.com/ваш-username/speech-engine.git
```

### Ошибка авторизации при push

**Решение 1:** Используйте Personal Access Token вместо пароля:
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token → выберите права `repo`
3. Используйте токен как пароль при push

**Решение 2:** Используйте GitHub Desktop (графический интерфейс)

### Ошибка "branch 'main' does not exist"

```bash
# Создайте ветку main
git checkout -b main

# Или используйте master (старое название)
git push -u origin master
```

---

## Пример полной последовательности команд

```bash
# 1. Перейти в папку проекта
cd F:\speech-engine

# 2. Инициализировать Git
git init

# 3. Добавить все файлы
git add .

# 4. Создать первый коммит
git commit -m "Initial commit: Speech Engine STT/TTS"

# 5. Добавить удалённый репозиторий (ЗАМЕНИТЕ URL!)
git remote add origin https://github.com/ваш-username/speech-engine.git

# 6. Переименовать ветку в main
git branch -M main

# 7. Загрузить на GitHub
git push -u origin main
```

---

**Готово!** После этого ваш код будет на GitHub и доступен заказчику.
