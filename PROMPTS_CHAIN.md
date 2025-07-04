# Цепочка промптов и архитектура агентов CustDev Bot

## Оглавление
1. [Архитектура системы](#архитектура-системы)
2. [ResearcherAgent - Агент исследователя](#researcheragent---агент-исследователя)
3. [RespondentAgent - Агент респондента](#respondentagent---агент-респондента)
4. [Поток данных между агентами](#поток-данных-между-агентами)
5. [Визуальная схема](#визуальная-схема)

## Архитектура системы

Система состоит из двух основных агентов:

- **ResearcherAgent** - взаимодействует с исследователем, собирает параметры исследования
- **RespondentAgent** - проводит интервью с респондентами на основе полученных параметров

### Основные компоненты:
- **LLM**: GPT-4o (temperature=0.7)
- **Memory**: Zep Cloud для хранения контекста диалогов
- **Database**: Supabase для хранения интервью и ответов
- **Voice**: OpenAI Whisper для распознавания голосовых сообщений

## ResearcherAgent - Агент исследователя

**Файл**: `src/agents/researcher_agent.py`

### 1. Сбор параметров исследования (строки 25-31)

```python
self.fields_to_collect = {
    "research_goal": "Цель исследования",
    "audience": "Целевая аудитория", 
    "hypotheses": "Гипотезы для проверки",
    "style": "Стиль общения",
    "topic": "Тема и контекст"
}
```

### 2. Первый вопрос исследователю (строка 69)

```
"Какова основная цель вашего исследования? Что вы хотите узнать или понять?"
```

### 3. Промпт для анализа ответов исследователя

**Расположение**: строки 151-180  
**Назначение**: Извлечение структурированных данных из свободных ответов

```
Проанализируй ответ пользователя на вопрос и извлеки информацию для полей кастдев-исследования.

Последний заданный вопрос:
{last_question}

Ответ пользователя:
{text}

Уже собранные поля:
{current_fields}

Все необходимые поля и их описания:
{all_fields}

ВАЖНО: Пользователь может отвечать неточно или кратко. Попробуй понять смысл ответа в контексте заданного вопроса.

Примеры сопоставления:
- Вопрос о цели -> "узнать боли клиентов" = research_goal: "Выявление болей и потребностей клиентов"
- Вопрос о цели -> "аудитория моих клиентов" = research_goal: "Исследование целевой аудитории"
- Вопрос об аудитории -> "предприниматели" = audience: "Предприниматели"

Верни ТОЛЬКО валидный JSON объект с извлеченными полями (без markdown разметки).
```

### 4. Промпт для генерации следующего вопроса

**Расположение**: строки 222-248  
**Назначение**: Естественное продолжение диалога для сбора недостающей информации

```
Сгенерируй естественный уточняющий вопрос для сбора недостающей информации.

Последний ответ пользователя:
{last_answer}

Уже собрано:
{collected}

Недостает:
{missing}

Описания полей:
{descriptions}

ВАЖНО: Начни ответ с подтверждения того, что ты понял последний ответ пользователя.
Затем задай конкретный вопрос о ОДНОМ из недостающих полей.

Примеры хороших ответов:
- "Понял, вы хотите исследовать потребности мамочек 30-40 лет. Какие конкретно аспекты их поведения или предпочтений вас интересуют?"
- "Отлично, ваша цель - выявить боли клиентов в сфере детских товаров. Какие гипотезы вы хотите проверить в ходе исследования?"
- "Хорошо, я понял что вы работаете с предпринимателями. В каком стиле должен общаться бот с респондентами - более формальном или дружеском?"
```

### 5. Промпт для генерации инструкции

**Файл**: `src/prompts/instruction_generator.txt`  
**Вызов**: строки 301-311 в researcher_agent.py

```
Создай подробную инструкцию для проведения кастдев-интервью на основе данных исследователя.

Данные исследователя:
{fields}

Инструкция должна:
1. Быть понятной и дружелюбной
2. Объяснять цель интервью
3. Указывать примерное время прохождения
4. Описывать стиль общения
5. Мотивировать респондента дать развернутые ответы

Формат: короткий текст на 3-5 предложений, который будет показан респонденту в начале интервью.
```

## RespondentAgent - Агент респондента

**Файл**: `src/agents/respondent_agent.py`

### 1. Промпт для первого вопроса респонденту

**Расположение**: строки 157-168  
**Назначение**: Начало интервью с открытого вопроса

```
Ты проводишь кастдев-интервью по следующей инструкции:
{instruction}

Сгенерируй первый вопрос для респондента.
Вопрос должен быть открытым, дружелюбным и располагать к развернутому ответу.

Верни только текст вопроса, без лишних пояснений.
```

### 2. Промпт для генерации последующих вопросов

**Расположение**: строки 184-213  
**Назначение**: Продолжение интервью с учетом контекста

```
Ты проводишь кастдев-интервью по следующей инструкции:
{instruction}

История диалога:
{history}

Уже задано вопросов: {answers_count}

Сгенерируй следующий вопрос, который:
1. Начинается с краткого подтверждения понимания последнего ответа
2. Логично вытекает из предыдущего ответа
3. Углубляет понимание темы
4. Побуждает к развернутому ответу
5. Соответствует инструкции исследования

Примеры хороших ответов:
- "Понимаю, для вас важна экономия времени. А какие еще факторы влияют на ваш выбор?"
- "Интересно, что вы упомянули качество материалов. Расскажите подробнее, с какими проблемами вы сталкивались?"

ВАЖНО: Продолжай задавать уточняющие вопросы, пока не получишь хотя бы 3-5 развернутых ответов.
Верни "FINISH" ТОЛЬКО если:
- Задано 5 или более вопросов
- ИЛИ респондент явно просит закончить
- ИЛИ получена полная информация по всем аспектам инструкции

Верни только текст вопроса или "FINISH", без лишних пояснений.
```

### 3. Промпт для генерации резюме

**Расположение**: строки 299-309  
**Назначение**: Создание краткого резюме для исследователя

```
Проанализируй ответы респондента и создай краткое резюме (3-5 предложений).

Вопросы и ответы:
{qa_text}

Выдели ключевые инсайты, боли, потребности и пожелания респондента.
Пиши кратко и по существу.
```

## Поток данных между агентами

### 1. Фаза сбора данных (ResearcherAgent)
1. Исследователь начинает с команды `/start`
2. Бот задает первый вопрос о цели исследования
3. Через промпты анализирует ответы и извлекает поля
4. Генерирует следующие вопросы до заполнения всех полей
5. Создает инструкцию на основе собранных данных
6. Генерирует уникальную ссылку для респондентов

### 2. Передача данных
- Собранные поля сохраняются в таблице `interviews` в Supabase
- ID исследователя сохраняется в `fields.researcher_telegram_id`
- Инструкция сохраняется в `fields.instruction`

### 3. Фаза интервью (RespondentAgent)
1. Респондент переходит по ссылке с ID интервью
2. Бот загружает инструкцию из базы данных
3. Генерирует первый вопрос на основе инструкции
4. Проводит интервью (3-5 вопросов)
5. Сохраняет ответы в `user_sessions.state.answers`

### 4. Возврат результатов
- После завершения интервью генерируется резюме
- Резюме отправляется исследователю по сохраненному ID
- Полные ответы сохраняются в базе данных

## Визуальная схема

```
┌─────────────────┐
│  Исследователь  │
└────────┬────────┘
         │ /start
         ▼
┌─────────────────┐     ┌──────────────┐
│ ResearcherAgent │────▶│   Промпты:   │
│                 │     │ - Анализ     │
│ Сбор 5 полей:  │     │ - Вопросы    │
│ - Цель         │     │ - Инструкция │
│ - Аудитория    │     └──────────────┘
│ - Гипотезы     │
│ - Стиль        │
│ - Тема         │
└────────┬────────┘
         │ 
         ▼
┌─────────────────┐
│    Supabase     │
│   interviews    │
│  (инструкция)   │
└────────┬────────┘
         │ Ссылка
         ▼
┌─────────────────┐
│   Респондент    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ RespondentAgent │────▶│   Промпты:   │
│                 │     │ - 1й вопрос  │
│ Интервью:       │     │ - Следующие  │
│ - 3-5 вопросов  │     │ - Резюме     │
│ - История в Zep │     └──────────────┘
│ - Голос/текст   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Резюме      │
│        ↓        │
│  Исследователь  │
└─────────────────┘
```

## Ключевые особенности

1. **Контекстность**: Каждый промпт учитывает предыдущий контекст диалога
2. **Гибкость**: Промпты адаптируются под стиль и тему исследования
3. **Естественность**: Вопросы начинаются с подтверждения понимания
4. **Ограничения**: Максимум 5 вопросов для респондента
5. **Обратная связь**: Резюме автоматически отправляется исследователю