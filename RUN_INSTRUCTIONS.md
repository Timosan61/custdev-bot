# 🚀 Инструкция по запуску Кастдев-бота

## ✅ Требования

- Python 3.11+
- Установленный ffmpeg (для обработки голосовых сообщений)
- Активные API ключи:
  - Telegram Bot Token
  - OpenAI API Key
  - Zep Cloud API Key
  - Supabase проект

## 📝 Быстрый старт

### 1. Проверка готовности

Запустите тестовый скрипт:

```bash
python3 test_bot.py
```

Вы должны увидеть:
- ✅ Все переменные окружения найдены
- ✅ Supabase подключен
- ✅ Таблица interviews доступна
- ✅ Zep Cloud подключен
- ✅ OpenAI API подключен
- ✅ Бот запущен: @castdevrun_bot

### 2. Запуск бота

```bash
python3 -m src.main
```

### 3. Проверка работы

1. Откройте Telegram и найдите бота @castdevrun_bot
2. Отправьте команду `/start`
3. Выберите "🔬 Создать исследование"

## 🛠 Установка зависимостей (если требуется)

Если у вас есть виртуальное окружение:

```bash
pip install aiogram==3.15.0
pip install langchain==0.3.13
pip install langchain-openai==0.2.14
pip install openai==1.58.1
pip install supabase==2.11.2
pip install zep-cloud==1.1.3
pip install pydub==0.25.1
pip install python-dotenv==1.0.1
pip install loguru==0.7.3
```

## 🐳 Docker (альтернативный способ)

```bash
docker-compose up -d
```

## 🔍 Отладка

Если бот не запускается:

1. Проверьте логи:
   ```bash
   # Смотрим последние логи
   tail -f logs/bot.log
   ```

2. Проверьте переменные окружения:
   ```bash
   cat .env | grep -E "TELEGRAM|OPENAI|ZEP|SUPABASE"
   ```

3. Проверьте доступность Telegram API:
   ```bash
   curl https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe
   ```

## 📊 Мониторинг

### База данных

Проверить таблицы в Supabase:
- `interviews` - созданные исследования
- `respondent_answers` - ответы респондентов
- `user_sessions` - активные сессии

### Telegram команды

- `/start` - главное меню
- `/help` - справка
- `/cancel` - отмена текущего действия

## ⚠️ Известные проблемы

1. **Предупреждение о ffmpeg**: Если видите предупреждение о ffmpeg, установите его:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

2. **Ошибка с виртуальным окружением**: Используйте системный Python или Docker

3. **Timeout ошибки**: Увеличьте таймауты в настройках бота

## 🆘 Поддержка

При возникновении проблем:
1. Запустите `test_bot.py` для диагностики
2. Проверьте файл `tasks.md` для списка реализованных функций
3. Смотрите логи в консоли при запуске с флагом DEBUG