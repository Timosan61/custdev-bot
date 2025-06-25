from typing import Dict, Optional
from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from loguru import logger
import json
import re
import os

from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService
from src.services.voice_handler import VoiceMessageHandler
from src.utils.keyboards import get_cancel_keyboard
from src.state.user_states import ResearcherStates

class ResearcherAgent:
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        self.supabase = supabase
        self.zep = zep
        # Initialize voice handler with bot token
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.voice_handler = VoiceMessageHandler(bot_token=bot_token)
        self.llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
        
        # Статичные вопросы и поля
        self.static_questions = {
            "name": "Как к вам обращаться?",
            "industry": "В какой сфере, нише или контексте проводится исследование?",
            "target": "Кого / что вы планируете изучать? Опишите, пожалуйста:\n1) если это люди — сегмент, роль, возраст, географию;\n2) если это процессы или продукт — его этапы/функции, где «болит».",
            "hypotheses": "Какие рабочие гипотезы или предположения хотите проверить? Сформулируйте «если … то … → ожидаемый эффект».",
            "style": "В каком тоне общаться с респондентами? Выберите или сформулируйте свой вариант:\n• Дружелюбно, на «ты»\n• Нейтрально-деловой, на «вы»\n• Эксперт–эксперт (термины допускаются)\n• Лайтово с юмором",
            "success_metric": "По каким метрикам вы поймёте, что исследование успешно?\nНапр.: «найти 3 ключевые мотивации», «подтвердить/опровергнуть 2 гипотезы».",
            "constraints": "Есть ли ограничения: время интервью, темы-табу, юридические требования (NDA/GDPR)?",
            "existing_data": "Есть ли уже собранные данные/аналитика, на которые стоит опираться?\nМожно загрузить файл (PDF, txt, docx) или краткое описание."
        }
        
        # Обязательные и необязательные поля
        self.required_fields = ["name", "industry", "target", "hypotheses", "style"]
        self.optional_fields = ["success_metric", "constraints", "existing_data"]
        
        # Порядок задавания вопросов
        self.question_order = self.required_fields + self.optional_fields
        
        # Для обратной совместимости
        self.fields_to_collect = self.static_questions
    
    async def start_dialog(self, message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        
        # Create new interview
        interview = self.supabase.create_interview({"researcher_telegram_id": user_id})
        if not interview:
            await message.answer("❌ Ошибка создания интервью")
            return
        interview_id = interview["id"]
        
        # Create Zep session
        zep_session_id = f"researcher_{user_id}_{interview_id}"
        await self.zep.create_session(zep_session_id, {
            "user_id": user_id,
            "interview_id": interview_id,
            "type": "researcher"
        })
        
        # Save to state
        await state.update_data(
            interview_id=interview_id,
            zep_session_id=zep_session_id,
            collected_fields={}
        )
        
        # Send welcome message and first question
        welcome_text = (
            "🔬 <b>Создание нового исследования</b>\n\n"
            "Привет! Я помогу вам создать кастдев-интервью.\n\n"
            "Отвечайте на мои вопросы в свободной форме текстом или голосом. "
            "Когда закончите, скажите 'хватит' или нажмите кнопку завершения."
        )
        
        await message.answer(welcome_text, reply_markup=types.ReplyKeyboardRemove())
        
        # Ask first question from static questions
        first_field = self.question_order[0]
        first_question = self.static_questions[first_field]
        await message.answer(first_question)
        
        # Track current field index
        await state.update_data(current_field_index=0)
        
        # Save first question in state
        await state.update_data(last_question=first_question)
        
        # Log to Zep
        await self.zep.add_message(zep_session_id, "assistant", welcome_text)
        await self.zep.add_message(zep_session_id, "assistant", first_question)
    
    async def process_text_message(self, message: types.Message, state: FSMContext):
        await self._process_message(message.text, message, state)
    
    async def process_voice_message(self, message: types.Message, state: FSMContext, bot: Bot):
        # Send processing indicator
        processing_msg = await message.answer("🎤 Обрабатываю голосовое сообщение...")
        
        # Process voice message
        result = await self.voice_handler.process_voice_message(
            file_id=message.voice.file_id,
            duration=message.voice.duration
        )
        
        # Delete processing message
        await bot.delete_message(message.chat.id, processing_msg.message_id)
        
        if result["success"]:
            text = result["transcription"]
            logger.info(f"Voice transcribed: {text}")
            
            # Process the message
            await self._process_message(text, message, state)
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"Voice processing failed: {error}")
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте еще раз или отправьте текстом.")
    
    async def _process_message(self, text: str, message: types.Message, state: FSMContext):
        data = await state.get_data()
        user_id = message.from_user.id
        interview_id = data.get("interview_id")
        zep_session_id = data.get("zep_session_id")
        collected_fields = data.get("collected_fields", {})
        current_field_index = data.get("current_field_index", 0)
        current_field = self.question_order[current_field_index] if current_field_index < len(self.question_order) else None
        is_clarification = data.get("is_clarification", False)
        
        logger.info(f"Processing message from user {user_id}: {text[:50]}...")
        logger.debug(f"Current field: {current_field}, Index: {current_field_index}")
        logger.debug(f"Is clarification: {is_clarification}")
        
        # Базовая проверка для обязательных полей
        if current_field in self.required_fields:
            text_lower = text.lower().strip()
            # Список стоп-слов для обязательных полей
            stop_words = ["не знаю", "незнаю", "не понимаю", "хз", "фиг знает", "понятия не имею"]
            
            # Проверка на стоп-слова
            if any(stop_word in text_lower for stop_word in stop_words):
                logger.warning(f"Stop word detected in answer for {current_field}: {text}")
                await message.answer(
                    f"Пожалуйста, дайте более конкретный ответ. "
                    f"Это важно для настройки интервью под ваши задачи."
                )
                return
            
            # Проверка минимальной длины для некоторых полей
            min_lengths = {
                "industry": 5,
                "target": 10,
                "hypotheses": 15,
                "style": 5
            }
            
            if current_field in min_lengths and len(text.strip()) < min_lengths[current_field]:
                logger.warning(f"Answer too short for {current_field}: {len(text)} chars")
                await message.answer(
                    f"Ваш ответ слишком короткий. Пожалуйста, опишите подробнее."
                )
                return
        
        # Log user message to Zep
        await self.zep.add_message(zep_session_id, "user", text)
        
        # Check if user wants to finish
        if any(word in text.lower() for word in ["хватит", "достаточно", "все", "стоп"]):
            # Check if we have all required fields
            missing_required = [f for f in self.required_fields if f not in collected_fields]
            if missing_required:
                await message.answer(
                    f"❗ Для создания исследования нужно ответить на все обязательные вопросы.\n"
                    f"Осталось заполнить: {', '.join([self.static_questions[f][:30] + '...' for f in missing_required[:2]])}\n\n"
                    f"Хотите продолжить?"
                )
                return
            else:
                await self._finish_collection(message, state)
                return
        
        # Extract answer for current field
        if current_field:
            # Use field analyzer to check answer quality
            quality_result = await self._evaluate_answer_quality(current_field, text)
            
            logger.info(f"Quality evaluation for {current_field}: {quality_result}")
            
            if quality_result["is_complete"]:
                # Save the answer
                collected_fields[current_field] = quality_result["extracted_value"]
                await state.update_data(collected_fields=collected_fields, is_clarification=False)
                logger.info(f"Field {current_field} saved: {quality_result['extracted_value']}")
                
                # Move to next field
                next_index = current_field_index + 1
                
                # Skip optional fields if user said "no" or "skip"
                while next_index < len(self.question_order):
                    next_field = self.question_order[next_index]
                    if next_field in self.optional_fields and any(word in text.lower() for word in ["нет", "не надо", "пропустить", "skip"]):
                        logger.info(f"Skipping optional field: {next_field}")
                        next_index += 1
                    else:
                        break
                
                if next_index < len(self.question_order):
                    # Ask next static question
                    next_field = self.question_order[next_index]
                    next_question = self.static_questions[next_field]
                    await message.answer(next_question)
                    await self.zep.add_message(zep_session_id, "assistant", next_question)
                    await state.update_data(current_field_index=next_index, last_question=next_question)
                else:
                    # All questions asked
                    await self._finish_collection(message, state)
            else:
                # Need clarification
                if is_clarification:
                    # This was already a clarification attempt, accept the answer anyway
                    collected_fields[current_field] = text
                    await state.update_data(collected_fields=collected_fields, is_clarification=False)
                    
                    # Move to next field
                    next_index = current_field_index + 1
                    if next_index < len(self.question_order):
                        next_field = self.question_order[next_index]
                        next_question = self.static_questions[next_field]
                        await message.answer(next_question)
                        await self.zep.add_message(zep_session_id, "assistant", next_question)
                        await state.update_data(current_field_index=next_index, last_question=next_question)
                    else:
                        await self._finish_collection(message, state)
                else:
                    # Generate clarification question
                    clarification = await self._generate_clarification(
                        current_field,
                        text,
                        quality_result["missing_aspects"]
                    )
                    await message.answer(clarification)
                    await self.zep.add_message(zep_session_id, "assistant", clarification)
                    await state.update_data(is_clarification=True, last_question=clarification)
    
    async def _evaluate_answer_quality(self, field: str, answer: str) -> Dict:
        """Оценивает качество ответа на вопрос"""
        with open("src/prompts/field_analyzer.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["field_name", "field_description", "question", "answer"],
            template=template
        )
        
        field_description = {
            "name": "Имя или обращение к исследователю",
            "industry": "Сфера деятельности или ниша бизнеса",
            "target": "Целевая аудитория или объект исследования с конкретными характеристиками",
            "hypotheses": "Конкретные гипотезы в формате если...то...",
            "style": "Стиль общения с респондентами",
            "success_metric": "Метрики успеха исследования",
            "constraints": "Ограничения по времени, темам или другие требования",
            "existing_data": "Информация о существующих данных или исследованиях"
        }
        
        try:
            response = await self.llm.ainvoke(
                prompt.format(
                    field_name=field,
                    field_description=field_description.get(field, ""),
                    question=self.static_questions.get(field, ""),
                    answer=answer
                )
            )
            
            # Parse JSON response
            content = response.content.strip()
            logger.debug(f"LLM response for {field}: {content[:200]}...")
            
            if content.startswith("```json") and content.endswith("```"):
                content = content[7:-3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()
            
            result = json.loads(content)
            logger.debug(f"Parsed result for {field}: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in evaluate_answer_quality: {e}")
            logger.error(f"Response content: {content[:200]}...")
            # При ошибке парсинга JSON не принимаем ответ автоматически
            return {
                "is_complete": False,
                "confidence": 0.0,
                "missing_aspects": ["Не удалось проанализировать ответ"],
                "extracted_value": None
            }
        except Exception as e:
            logger.error(f"Error evaluating answer quality: {e}", exc_info=True)
            # При других ошибках тоже не принимаем ответ автоматически
            return {
                "is_complete": False,
                "confidence": 0.0,
                "missing_aspects": ["Произошла ошибка при анализе"],
                "extracted_value": None
            }
    
    async def _generate_clarification(self, field: str, answer: str, missing_aspects: list) -> str:
        """Генерирует уточняющий вопрос"""
        with open("src/prompts/clarification_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["field_name", "original_question", "answer", "missing_aspects", "conversation_history"],
            template=template
        )
        
        response = await self.llm.ainvoke(
            prompt.format(
                field_name=field,
                original_question=self.static_questions[field],
                answer=answer,
                missing_aspects=missing_aspects,
                conversation_history=""  # Can be enhanced with actual history
            )
        )
        
        return response.content.strip()
    
    async def _generate_interview_brief(self, fields: Dict) -> str:
        """Генерирует интервью-бриф на основе собранных данных"""
        with open("src/prompts/interview_brief_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["answers"],
            template=template
        )
        
        # Just pass the fields as they are, let the LLM handle formatting
        response = await self.llm.ainvoke(
            prompt.format(answers=json.dumps(fields, ensure_ascii=False, indent=2))
        )
        
        return response.content
    
    async def _finish_collection(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        interview_id = data.get("interview_id")
        collected_fields = data.get("collected_fields", {})
        
        try:
            # Generate interview brief
            interview_brief = await self._generate_interview_brief(collected_fields)
            
            # Extract instruction from brief (first message to respondent)
            # Simple extraction - find the section and get the content
            instruction_start = interview_brief.find("### 3. Первое сообщение респонденту")
            if instruction_start != -1:
                instruction_text = interview_brief[instruction_start:]
                instruction_lines = instruction_text.split("\n")[2:]  # Skip header and empty line
                instruction = "\n".join(instruction_lines).strip()
            else:
                # Fallback to generating instruction the old way
                instruction = await self._generate_instruction(collected_fields)
            
            # Update interview
            # Сохраняем researcher_telegram_id в fields для обратной совместимости
            collected_fields["researcher_telegram_id"] = message.from_user.id
            
            update_data = {
                "status": "in_progress",
                "fields": collected_fields,
                "researcher_telegram_id": message.from_user.id  # Сохраняем на верхнем уровне
            }
            
            # Добавляем instruction если колонка существует
            if instruction:
                update_data["instruction"] = instruction
                # Также сохраняем в fields для обратной совместимости
                update_data["fields"]["instruction"] = instruction
            
            # Пока сохраняем все поля только в JSONB fields
            # После выполнения миграций можно будет добавить сохранение на верхний уровень
            
            try:
                self.supabase.update_interview(interview_id, update_data)
            except Exception as e:
                logger.error(f"Error updating interview: {e}")
                await message.answer(
                    "❌ Произошла ошибка при сохранении брифа исследования.\n"
                    "Пожалуйста, попробуйте позже или обратитесь к администратору."
                )
                await state.clear()
                return
        
            # Generate interview link
            bot_username = (await message.bot.me()).username
            interview_link = f"https://t.me/{bot_username}?start=interview_{interview_id}"
            
            # Персонализированное сообщение с использованием имени
            researcher_name = collected_fields.get("name", "")
            greeting = f"Отлично, {researcher_name}! " if researcher_name else ""
            
            # Send interview brief as a message
            brief_text = (
                f"✅ <b>{greeting}Исследование создано!</b>\n\n"
                f"<b>Ссылка для респондентов:</b>\n"
                f"{interview_link}\n\n"
                "📄 <b>Интервью-бриф:</b>\n\n"
            )
            
            # Send brief in parts to avoid message length limits
            await message.answer(brief_text, reply_markup=types.ReplyKeyboardRemove())
            
            # Send the interview brief
            await message.answer(interview_brief, parse_mode="Markdown")
            
            # Optionally save brief as a file
            # TODO: Implement file generation and sending
            
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error in _finish_collection: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при создании исследования.\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            await state.clear()
    
    async def _generate_instruction(self, fields: Dict) -> str:
        with open("src/prompts/instruction_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["fields"],
            template=template
        )
        
        response = await self.llm.ainvoke(prompt.format(fields=fields))
        return response.content
    
    def _is_valid_url(self, text: str) -> bool:
        """Проверяет, является ли текст валидной ссылкой"""
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(text.strip()))