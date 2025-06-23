# Кастдев-бот Telegram MVP

Telegram-бот для проведения кастдев-интервью в режиме живого диалога.

## Функционал

- 🔬 **Для исследователей**: живой диалог для сбора информации об исследовании
- 📊 **Для респондентов**: прохождение интервью по сгенерированной инструкции
- 🎤 **Поддержка голосовых сообщений** через Whisper API
- 💾 **Сохранение контекста** через Zep Cloud
- 🤖 **Умная генерация вопросов** с помощью GPT-4

## Установка

### Требования

- Python 3.11+
- PostgreSQL (через Supabase)
- Telegram Bot Token
- OpenAI API Key
- Zep Cloud API Key

### Локальный запуск

1. Клонируйте репозиторий
2. Создайте виртуальное окружение:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # или
   venv\Scripts\activate  # Windows
   ```

3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

4. Скопируйте `.env.example` в `.env` и заполните переменные

5. Запустите бота:
   ```bash
   python -m src.main
   ```

### Docker

```bash
docker-compose up -d
```

## Структура проекта

```
custdev-bot/
├── src/
│   ├── bot/               # Telegram handlers
│   ├── agents/            # AI agents
│   ├── prompts/           # LLM prompts
│   ├── services/          # External services
│   ├── state/             # FSM states
│   └── utils/             # Utilities
├── data/                  # Data files
├── requirements.txt       # Dependencies
└── docker-compose.yml     # Docker config
```

## Использование

### Для исследователей

1. Отправьте `/start` боту
2. Выберите "🔬 Создать исследование"
3. Ответьте на вопросы бота о вашем исследовании
4. Получите ссылку для респондентов

### Для респондентов

1. Перейдите по ссылке от исследователя
2. Отвечайте на вопросы интервью
3. Используйте кнопки для навигации

## База данных

Структура таблиц в Supabase:

- `interviews` - данные исследований
- `respondent_answers` - ответы респондентов
- `user_sessions` - сессии пользователей

## Разработка

См. файл `tasks.md` для списка задач по разработке.

## Лицензия

MIT