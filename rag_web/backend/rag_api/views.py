"""
Django API views для RAG системы.
"""

import logging
import json
import requests
import pandas as pd
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import sys
import os
import threading
import queue
import time

# Добавляем путь к корневому каталогу проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, BASE_DIR)

try:
    from test_final_v2 import RAGSystemLangChain
    from gigachat import GigaChat
    from .token_stats import record_from_response, save_stats_to_file
except ImportError as e:
    logging.error(f"Ошибка импорта: {e}")
    logging.error(f"BASE_DIR: {BASE_DIR}")
    logging.error(f"sys.path: {sys.path}")
    raise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Учетные данные GigaChat
GIGACHAT_CREDENTIALS = "MDE5OWUyNTAtNGNhZS03ZDdjLTg2ZmMtZjM5NDE0ZGFhNjUzOmYzMTk3ZWUyLTBlNTYtNDUzNy04ZWViLTUyZWU4ZjAyZGMzZA=="

# Глобальный экземпляр RAG системы (инициализируется при первом запросе)
_rag_system = None

# Глобальное хранилище прогресса для каждого запроса
_progress_storage = {}


def get_rag_system():
    """Получение или создание экземпляра RAG системы."""
    global _rag_system
    if _rag_system is None:
        logger.info("Инициализация RAG системы...")
        
        # Получаем настройки OpenSearch из переменных окружения
        opensearch_host = os.environ.get('OPENSEARCH_HOST', 'localhost')
        opensearch_port = int(os.environ.get('OPENSEARCH_PORT', 9200))
        opensearch_use_ssl = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
        opensearch_verify_certs = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
        
        # Настройка аутентификации (если указана)
        opensearch_auth = None
        opensearch_username = os.environ.get('OPENSEARCH_AUTH_USERNAME')
        opensearch_password = os.environ.get('OPENSEARCH_AUTH_PASSWORD')
        if opensearch_username and opensearch_password:
            opensearch_auth = (opensearch_username, opensearch_password)
        
        logger.info(f"Подключение к OpenSearch: {opensearch_host}:{opensearch_port} (SSL: {opensearch_use_ssl})")
        
        _rag_system = RAGSystemLangChain(
            opensearch_host=opensearch_host,
            opensearch_port=opensearch_port,
            opensearch_use_ssl=opensearch_use_ssl,
            opensearch_verify_certs=opensearch_verify_certs,
            opensearch_auth=opensearch_auth,
            opensearch_index_descriptions="feature_descriptions",
            opensearch_index_layers="rag_layers",
            credentials=GIGACHAT_CREDENTIALS
        )
        logger.info("RAG система инициализирована")
    return _rag_system




def _send_progress_event(progress_storage, step, progress, message, details=None):
    """Обновление прогресса в хранилище."""
    if progress_storage:
        progress_storage['step'] = step
        progress_storage['progress'] = progress
        progress_storage['message'] = message
        progress_storage['details'] = details or {}
        logger.info(f"Обновление прогресса: step={step}, progress={progress}%, message={message[:50] if message else ''}")


def _rag_query_with_progress(rag_system, user_query, progress_storage, top_k=20):
    """
    Выполнение RAG запроса с отправкой прогресса.
    
    Шаги:
    1. Генерация описания признака/запроса (0-20%)
    2. Поиск в OpenSearch (20-40%)
    3. Проверка признаков (40-60%)
    4. Генерация и выполнение SQL запросов (60-85%)
    5. Генерация финального ответа (85-100%)
    """
    try:
        # Шаг 1: Генерация описания признака/запроса (0-20%)
        _send_progress_event(progress_storage, 1, 5, "ШАГ 1: Генерация описания признака/запроса...")
        feature_description = rag_system.generate_feature_description(user_query)
        _send_progress_event(progress_storage, 1, 20, f"Описание сгенерировано: {feature_description[:50]}...")
        
        # Шаг 2: Поиск в OpenSearch (20-40%)
        _send_progress_event(progress_storage, 2, 25, f"ШАГ 2: Поиск в OpenSearch (топ-{top_k})...")
        search_results = rag_system.search_in_opensearch(feature_description, top_k=top_k)
        
        if not search_results:
            _send_progress_event(progress_storage, 2, 40, "Не найдено результатов в OpenSearch", {'found': 0})
            return pd.DataFrame(), "К сожалению, по вашему запросу не найдено релевантных признаков в базе."
        
        _send_progress_event(progress_storage, 2, 40, f"Найдено {len(search_results)} результатов в OpenSearch", {'found': len(search_results)})
        
        # Шаг 3: Проверка признаков (40-60%)
        _send_progress_event(progress_storage, 3, 45, f"ШАГ 3: Проверка {len(search_results)} признаков...")
        matched_features = []
        
        for idx, doc in enumerate(search_results):
            feature_name = doc.metadata.get('feature_name', '')
            if not feature_name:
                feature_name = doc.metadata.get('name', '')
            if not feature_name:
                text = doc.page_content or ""
                parts = text.split('\n')
                for part in parts[:3]:
                    part = part.strip()
                    if part and len(part) < 100:
                        feature_name = part
                        break
            
            feature_desc = doc.page_content if doc.page_content else ""
            if not feature_desc:
                feature_desc = doc.metadata.get('description', '')
            feature_desc = feature_desc[:1000] if feature_desc else ""
            
            if not feature_name:
                continue
            
            # Прогресс проверки каждого признака
            check_progress = 45 + int((idx + 1) / len(search_results) * 15)
            _send_progress_event(progress_storage, 3, check_progress, f"Проверка признака {idx + 1}/{len(search_results)}: {feature_name[:30]}...")
            
            if rag_system.check_feature_match(user_query, feature_name, feature_desc):
                matched_features.append({
                    'feature_name': feature_name,
                    'description': feature_desc,
                    'doc': doc
                })
        
        if not matched_features:
            _send_progress_event(progress_storage, 3, 60, "Не найдено признаков, соответствующих запросу")
            return pd.DataFrame(), "К сожалению, не найдено признаков, соответствующих вашему запросу."
        
        _send_progress_event(progress_storage, 3, 60, f"Найдено {len(matched_features)} соответствующих признаков", {'matched': len(matched_features)})
        
        # Шаг 4: Генерация и выполнение SQL запросов (60-85%)
        _send_progress_event(progress_storage, 4, 65, "ШАГ 4: Генерация и выполнение SQL запросов...")
        all_results = []
        
        for idx, feature_info in enumerate(matched_features):
            feature_name = feature_info['feature_name']
            feature_desc = feature_info['description']
            
            sql_progress = 65 + int((idx + 1) / len(matched_features) * 20)
            _send_progress_event(progress_storage, 4, sql_progress, f"Генерация SQL для признака {idx + 1}/{len(matched_features)}: {feature_name[:30]}...")
            
            sql_query = rag_system.generate_sql_query(user_query, feature_name, feature_desc)
            
            if sql_query:
                _send_progress_event(progress_storage, 4, sql_progress + 2, f"Выполнение SQL запроса для {feature_name[:30]}...")
                result_df = rag_system.execute_sql_query(sql_query)
                
                if not result_df.empty:
                    result_df['matched_feature'] = feature_name
                    all_results.append(result_df)
                    _send_progress_event(progress_storage, 4, sql_progress + 4, f"Для признака '{feature_name}' найдено {len(result_df)} записей", {'records': len(result_df)})
        
        if all_results:
            combined_results = pd.concat(all_results, ignore_index=True)
            _send_progress_event(progress_storage, 4, 85, f"Всего найдено {len(combined_results)} записей", {'total_records': len(combined_results)})
        else:
            combined_results = pd.DataFrame()
            _send_progress_event(progress_storage, 4, 85, "SQL запросы не вернули результатов")
        
        # Шаг 5: Генерация финального ответа (85-100%)
        _send_progress_event(progress_storage, 5, 90, "ШАГ 5: Генерация финального ответа преподавателя...")
        final_answer = rag_system.generate_final_summary(user_query, combined_results)
        _send_progress_event(progress_storage, 5, 100, "Ответ сгенерирован", {'answer_length': len(final_answer)})
        
        # Сохраняем статистику токенов после завершения запроса
        try:
            save_stats_to_file()
        except Exception as e:
            logger.warning(f"Не удалось сохранить статистику токенов: {e}")
        
        return combined_results, final_answer
        
    except Exception as e:
        logger.error(f"Ошибка в _rag_query_with_progress: {e}", exc_info=True)
        if progress_storage:
            _send_progress_event(progress_storage, 0, 0, f"Ошибка: {str(e)}", {'error': str(e)})
        raise


@method_decorator(csrf_exempt, name='dispatch')
class QueryView(View):
    """API endpoint для обработки запросов пользователя с отслеживанием прогресса."""
    
    def post(self, request):
        """Обработка POST запроса с вопросом пользователя."""
        import uuid
        import threading
        
        try:
            data = json.loads(request.body)
            user_query = data.get('query', '').strip()
            
            if not user_query:
                return JsonResponse({
                    'error': 'Запрос не может быть пустым'
                }, status=400)
            
            logger.info(f"Получен запрос: {user_query}")
            
            # Создаем уникальный ID для этого запроса
            request_id = str(uuid.uuid4())
            
            # Инициализируем прогресс
            _progress_storage[request_id] = {
                'step': 0,
                'progress': 0,
                'message': 'Инициализация...',
                'details': {},
                'status': 'processing',
                'result': None,
                'error': None
            }
            
            # Получаем RAG систему
            rag_system = get_rag_system()
            
            # Запускаем запрос в отдельном потоке
            def run_query():
                try:
                    results_df, answer = _rag_query_with_progress(
                        rag_system, 
                        user_query, 
                        _progress_storage[request_id], 
                        top_k=20
                    )
                    
                    # Извлекаем координаты
                    coordinates = rag_system.extract_coordinates(results_df)
                    has_coordinates = len(coordinates) > 0
                    
                    # Сохраняем результат
                    _progress_storage[request_id]['result'] = {
                        'answer': answer,
                        'coordinates': coordinates,
                        'results_count': len(results_df) if not results_df.empty else 0,
                        'has_coordinates': has_coordinates
                    }
                    _progress_storage[request_id]['status'] = 'completed'
                    _progress_storage[request_id]['progress'] = 100
                    _progress_storage[request_id]['step'] = 6
                    _progress_storage[request_id]['message'] = 'Запрос выполнен успешно'
                    
                except Exception as e:
                    logger.error(f"Ошибка выполнения запроса: {e}", exc_info=True)
                    _progress_storage[request_id]['status'] = 'error'
                    _progress_storage[request_id]['error'] = str(e)
            
            thread = threading.Thread(target=run_query)
            thread.start()
            
            # Возвращаем ID запроса для отслеживания прогресса
            return JsonResponse({
                'request_id': request_id,
                'status': 'started'
            })
            
        except Exception as e:
            logger.error(f"Ошибка обработки запроса: {e}", exc_info=True)
            return JsonResponse({
                'error': f'Ошибка обработки запроса: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class QueryProgressView(View):
    """API endpoint для получения прогресса выполнения запроса."""
    
    def get(self, request):
        """Получение текущего прогресса запроса."""
        request_id = request.GET.get('request_id')
        
        if not request_id:
            return JsonResponse({
                'error': 'request_id обязателен'
            }, status=400)
        
        if request_id not in _progress_storage:
            return JsonResponse({
                'error': 'Запрос не найден'
            }, status=404)
        
        progress_data = _progress_storage[request_id].copy()
        
        # Если запрос завершен, удаляем его из хранилища через некоторое время
        if progress_data['status'] in ['completed', 'error']:
            # Удаляем через 30 секунд после завершения
            import threading
            def cleanup():
                import time
                time.sleep(30)
                if request_id in _progress_storage:
                    del _progress_storage[request_id]
            threading.Thread(target=cleanup, daemon=True).start()
        
        return JsonResponse(progress_data)


@method_decorator(csrf_exempt, name='dispatch')
class QueryStreamView(View):
    """API endpoint для обработки запросов с SSE (Server-Sent Events) для прогресса."""
    
    def post(self, request):
        """Обработка POST запроса с отправкой прогресса через SSE."""
        def event_stream():
            try:
                data = json.loads(request.body)
                user_query = data.get('query', '').strip()
                
                if not user_query:
                    yield f"data: {json.dumps({'error': 'Запрос не может быть пустым'})}\n\n"
                    return
                
                logger.info(f"Получен запрос (SSE): {user_query}")
                
                # Создаем очередь для прогресса
                progress_queue = queue.Queue()
                
                # Получаем RAG систему
                rag_system = get_rag_system()
                
                # Запускаем запрос в отдельном потоке
                results_df = None
                answer = None
                error = None
                
                def run_query():
                    nonlocal results_df, answer, error
                    try:
                        results_df, answer = _rag_query_with_progress(rag_system, user_query, progress_queue, top_k=20)
                    except Exception as e:
                        error = str(e)
                        logger.error(f"Ошибка выполнения запроса: {e}", exc_info=True)
                
                query_thread = threading.Thread(target=run_query)
                query_thread.start()
                
                # Отправляем события прогресса
                logger.info("Начало отправки событий прогресса...")
                events_sent = 0
                while query_thread.is_alive() or not progress_queue.empty():
                    try:
                        # Получаем событие из очереди с таймаутом
                        event = progress_queue.get(timeout=0.1)
                        events_sent += 1
                        event_str = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        logger.info(f"[{events_sent}] Отправка события прогресса: step={event.get('step')}, progress={event.get('progress')}%, message={event.get('message')[:50] if event.get('message') else ''}")
                        yield event_str
                        # Принудительно отправляем данные (для некоторых серверов)
                        import sys
                        sys.stdout.flush()
                    except queue.Empty:
                        # Проверяем, жив ли поток
                        if not query_thread.is_alive():
                            logger.info(f"Поток завершен. Всего отправлено событий: {events_sent}")
                            break
                        continue
                
                logger.info(f"Завершение отправки событий. Всего отправлено: {events_sent}")
                
                # Ждем завершения потока
                query_thread.join()
                
                # Отправляем финальный результат
                if error:
                    yield f"data: {json.dumps({'error': error, 'step': 0, 'progress': 0})}\n\n"
                else:
                    # Извлекаем координаты
                    coordinates = rag_system.extract_coordinates(results_df)
                    has_coordinates = len(coordinates) > 0
                    
                    final_result = {
                        'step': 6,
                        'progress': 100,
                        'message': 'Запрос выполнен успешно',
                        'result': {
                            'answer': answer,
                            'coordinates': coordinates,
                            'results_count': len(results_df) if not results_df.empty else 0,
                            'has_coordinates': has_coordinates
                        }
                    }
                    yield f"data: {json.dumps(final_result)}\n\n"
                    
            except Exception as e:
                logger.error(f"Ошибка в event_stream: {e}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e), 'step': 0, 'progress': 0})}\n\n"
        
        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        # Отключаем буферизацию для мгновенной отправки
        # Примечание: Connection header нельзя устанавливать в WSGI, это hop-by-hop header
        return response


def prepare_video_text(full_answer: str, has_coordinates: bool = False, user_query: str = '') -> str:
    """
    Генерация текста для видео-аватара на основе полного ответа через GigaChat.
    Создает краткий, понятный текст для озвучивания аватаром.
    
    Args:
        full_answer: Полный ответ системы
        has_coordinates: Есть ли координаты в ответе
        user_query: Исходный запрос пользователя
        
    Returns:
        Краткий текст для видео-аватара
    """
    # Промпт для генерации текста видео
    video_prompt = f"""Ты - помощник, который готовит текст для озвучивания видео-аватаром.
        
Исходный вопрос пользователя: "{user_query}"

Полный ответ системы:
{full_answer}

Твоя задача - создать краткий, понятный текст для озвучивания видео-аватаром на основе этого ответа.

ТРЕБОВАНИЯ:
1. Текст должен быть кратким (до 1000 символов) и легко восприниматься на слух
2. Убери все технические детали, координаты и форматирование
3. Сохрани основную суть ответа и ключевые факты
4. Используй простой, разговорный стиль, подходящий для устного изложения
5. Если в ответе есть координаты или упоминание местоположения, обязательно скажи: "Координаты места можно увидеть на карте"
6. Текст должен быть естественным для произношения вслух
7. Не используй markdown, эмодзи или специальные символы
8. Используй короткие предложения

{"ВАЖНО: В тексте обязательно упомяни, что координаты можно увидеть на карте." if has_coordinates else ""}

Верни ТОЛЬКО текст для озвучивания, без дополнительных комментариев или форматирования."""

    try:
        model_name = 'GigaChat:light'
        logger.info("Генерация текста для видео-аватара через GigaChat...")
        with GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            verify_ssl_certs=False,
            scope='GIGACHAT_API_B2B',
            model=model_name
        ) as giga:
            response = giga.chat(video_prompt)
            record_from_response(model_name, response)
            video_text = response.choices[0].message.content.strip()
            
            # Очистка от возможных markdown блоков
            if video_text.startswith("```"):
                lines = video_text.split('\n')
                video_text = '\n'.join([line for line in lines if not line.strip().startswith('```')])
                video_text = video_text.strip()
            
            # Убеждаемся, что упоминание о карте есть, если есть координаты
            if has_coordinates and 'карт' not in video_text.lower() and 'координат' not in video_text.lower():
                video_text += " Координаты места можно увидеть на карте."
            
            logger.info(f"Сгенерирован текст для видео: {len(video_text)} символов")
            return video_text
            
    except Exception as e: 
        logger.error(f"Ошибка генерации текста для видео через GigaChat: {e}")
        # Fallback: простая очистка текста
        logger.warning("Используем fallback метод подготовки текста")
        lines = full_answer.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Пропускаем строки с координатами
            if any(keyword in line.lower() for keyword in ['📍', 'координат', 'lon:', 'lat:', 'долгота', 'широта']):
                continue
            # Пропускаем строки, которые выглядят как координаты
            if ',' in line and any(char.isdigit() for char in line) and len(line.strip()) < 50:
                continue
            cleaned_lines.append(line)
        
        video_text = '\n'.join(cleaned_lines).strip()
        
        # Добавляем информацию о координатах на карте, если они есть
        if has_coordinates:
            if 'карт' not in video_text.lower() and 'координат' not in video_text.lower():
                video_text += " Координаты места можно увидеть на карте."
        
        logger.info(f"Подготовлен текст для видео (fallback): {len(video_text)} символов")
        return video_text


def should_generate_video(answer: str) -> bool:
    """
    Проверяет, нужно ли генерировать видео на основе ответа.
    Не генерируем видео, если данных не найдено.
    
    Args:
        answer: Ответ системы
        
    Returns:
        True если нужно генерировать видео, False если нет
    """
    answer_lower = answer.lower()
    
    # Фразы, которые указывают на отсутствие данных
    no_data_phrases = [
        'не найдено',
        'не найдены',
        'данных нет',
        'данные не найдены',
        'результатов не найдено',
        'ничего не найдено',
        'к сожалению, по вашему запросу не найдено',
        'не удалось найти',
        'не обнаружено',
        'отсутствуют данные',
        'нет данных',
        'релевантных признаков в базе',
        'ошибка'
    ]
    
    # Проверяем наличие фраз об отсутствии данных
    for phrase in no_data_phrases:
        if phrase in answer_lower:
            logger.info(f"Видео не будет сгенерировано: обнаружена фраза '{phrase}'")
            return False
    
    return True


@method_decorator(csrf_exempt, name='dispatch') 
class HeyGenPrepareTextView(View):
    """API endpoint для подготовки текста для streaming аватара через GigaChat."""
    
    def post(self, request):
        """Подготовка текста для streaming аватара."""
        try:
            data = json.loads(request.body)
            full_answer = data.get('answer', '').strip()
            user_query = data.get('user_query', '').strip()
            has_coordinates = data.get('has_coordinates', False)
            
            if not full_answer:
                return JsonResponse({
                    'error': 'Ответ не может быть пустым'
                }, status=400)
            
            # Проверяем, нужно ли генерировать видео
            if not should_generate_video(full_answer):
                logger.info("Видео не будет сгенерировано: данные не найдены")
                return JsonResponse({
                    'error': 'Видео не генерируется, так как данные не найдены',
                    'skip_video': True
                }, status=200)
            
            # Генерируем текст для видео через GigaChat
            logger.info("Генерация текста для streaming аватара")
            video_text = prepare_video_text(full_answer, has_coordinates, user_query)
            
            # HeyGen API имеет ограничение на длину текста (обычно ~2000-2500 символов)
            # Обрезаем текст до разумного лимита, сохраняя целостность предложений
            MAX_TEXT_LENGTH = 2000  # Максимальная длина текста для HeyGen API
            if len(video_text) > MAX_TEXT_LENGTH:
                logger.warning(f"Текст для видео слишком длинный ({len(video_text)} символов), обрезаем до {MAX_TEXT_LENGTH}")
                # Обрезаем до последнего полного предложения перед лимитом
                truncated = video_text[:MAX_TEXT_LENGTH]
                # Ищем последнюю точку, восклицательный или вопросительный знак
                last_sentence_end = max(
                    truncated.rfind('. '),
                    truncated.rfind('! '),
                    truncated.rfind('? '),
                    truncated.rfind('.\n'),
                    truncated.rfind('!\n'),
                    truncated.rfind('?\n')
                )
                if last_sentence_end > MAX_TEXT_LENGTH * 0.7:  # Если нашли предложение в последних 30%
                    video_text = truncated[:last_sentence_end + 1] + " [текст обрезан из-за ограничений API]"
                else:
                    # Если не нашли подходящее место, просто обрезаем
                    video_text = truncated + " [текст обрезан из-за ограничений API]"
                logger.info(f"Текст обрезан до {len(video_text)} символов")
            
            # Возвращаем подготовленный текст для streaming
            return JsonResponse({
                'video_text': video_text,
                'skip_video': False
            }, status=200)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Неверный формат JSON'
            }, status=400)
        except Exception as e:
            logger.error(f"Ошибка генерации HeyGen видео: {e}", exc_info=True)
            return JsonResponse({
                'error': f'Ошибка обработки запроса: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class HeyGenStatusView(View):
    """API endpoint для проверки статуса видео HeyGen."""
    
    def get(self, request):
        """Проверка статуса видео по video_id."""
        video_id = request.GET.get("video_id")
        if not video_id:
            return JsonResponse({"error": "video_id обязателен"}, status=400)

        heygen_api_key = os.environ.get('HEYGEN_API_KEY', 'sk_V2_hgu_k1upmcGvBz3_QufVJuSjUjtPgAwTNhCwSKRGTzWqy9Hk')
        # Используем v1 API endpoint для статуса (как в heygen_test)
        heygen_status_url = os.environ.get('HEYGEN_STATUS_URL', 'https://api.heygen.com/v1/video_status.get')
        
        if not heygen_api_key:
            return JsonResponse(
                {"error": "HEYGEN_API_KEY не задан. Установите переменную окружения."},
                status=500,
            )

        try:
            response = requests.get(
                heygen_status_url,
                headers={
                    "X-Api-Key": heygen_api_key,
                    "Content-Type": "application/json",
                },
                params={"video_id": video_id},
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"HeyGen status network error: {e}")
            return JsonResponse({"error": f"Сеть/HTTP ошибка: {e}"}, status=502)

        if response.status_code >= 300:
            try:
                details = response.json()
            except:
                details = {"text": response.text}
            logger.error(
                "HeyGen status error: status=%s details=%s", response.status_code, details
            )
            return JsonResponse(
                {
                    "error": "HeyGen вернул ошибку статуса",
                    "status_code": response.status_code,
                    "details": details,
                },
                status=502,
            )

        try:
            data = response.json()
        except ValueError:
            data = {"text": response.text}
        
        logger.info(f"HeyGen status data: {data}")
        # v2 API returns {"data": {"status": "...", "video_url": "..."}}
        inner = data.get("data") or data
        status_value = inner.get("status") or inner.get("state")
        video_url = inner.get("video_url") or inner.get("url")

        return JsonResponse(
            {
                "status": status_value or "pending",
                "video_url": video_url,
                "raw": data,
            }
        )


@method_decorator(csrf_exempt, name='dispatch')
class HeyGenStreamingTokenView(View):
    """API endpoint для получения streaming токена HeyGen."""
    
    def post(self, request):
        """Получение streaming токена от HeyGen API."""
        heygen_api_key = os.environ.get('HEYGEN_API_KEY', 'sk_V2_hgu_k1upmcGvBz3_QufVJuSjUjtPgAwTNhCwSKRGTzWqy9Hk')
        
        if not heygen_api_key:
            return JsonResponse({"error": "HEYGEN_API_KEY не задан"}, status=500)

        try:
            response = requests.post(
                "https://api.heygen.com/v1/streaming.create_token",
                headers={
                    "X-Api-Key": heygen_api_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"HeyGen streaming token network error: {e}")
            return JsonResponse({"error": f"Сеть/HTTP ошибка: {e}"}, status=502)

        try:
            data = response.json()
        except ValueError:
            data = {"text": response.text}
        
        if response.status_code >= 300:
            logger.error(f"HeyGen streaming token error: status={response.status_code} details={data}")
            return JsonResponse({"error": "HeyGen error", "details": data}, status=502)

        logger.info("HeyGen streaming token получен успешно")
        
        # Добавляем avatar_id в ответ для использования на frontend
        # Получаем avatar_id из переменных окружения (без дефолтного значения, чтобы избежать использования несуществующего аватара)
        heygen_avatar_id = os.environ.get('HEYGEN_AVATAR_ID')
        if not heygen_avatar_id:
            logger.warning("HEYGEN_AVATAR_ID не задан в переменных окружения. Используйте доступный Interactive Avatar ID из https://labs.heygen.com/interactive-avatar")
            # Не используем дефолтное значение, так как старый аватар больше не доступен
            heygen_avatar_id = None
        
        # Если ответ содержит data, добавляем туда, иначе создаем новую структуру
        if isinstance(data, dict):
            if 'data' in data:
                data['data']['avatar_id'] = heygen_avatar_id
            else:
                data['avatar_id'] = heygen_avatar_id
        
        return JsonResponse(data)

