"""
Django API views для RAG системы.
"""

import logging
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import sys
import os

# Добавляем путь к корневому каталогу проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, BASE_DIR)

try:
    from test_final_v2 import RAGSystemLangChain
    from gigachat import GigaChat
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
            opensearch_index_descriptions="rag_descriptions",
            opensearch_index_layers="rag_layers",
            credentials=GIGACHAT_CREDENTIALS
        )
        logger.info("RAG система инициализирована")
    return _rag_system




@method_decorator(csrf_exempt, name='dispatch')
class QueryView(View):
    """API endpoint для обработки запросов пользователя."""
    
    def post(self, request):
        """Обработка POST запроса с вопросом пользователя."""
        try:
            data = json.loads(request.body)
            user_query = data.get('query', '').strip()
            
            if not user_query:
                return JsonResponse({
                    'error': 'Запрос не может быть пустым'
                }, status=400)
            
            logger.info(f"Получен запрос: {user_query}")
            
            # Получаем RAG систему
            rag_system = get_rag_system()
            
            # Выполняем запрос
            results_df, answer = rag_system.query(user_query=user_query, top_k=20)
            
            # Извлекаем координаты
            coordinates = rag_system.extract_coordinates(results_df)
            has_coordinates = len(coordinates) > 0
            
            # Формируем ответ
            response_data = {
                'answer': answer,
                'coordinates': coordinates,
                'results_count': len(results_df) if not results_df.empty else 0,
                'has_coordinates': has_coordinates
            }
            
            logger.info(f"Запрос обработан: найдено {len(coordinates)} координат, {len(results_df)} результатов")
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Ошибка обработки запроса: {e}", exc_info=True)
            return JsonResponse({
                'error': f'Ошибка обработки запроса: {str(e)}'
            }, status=500)


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
        logger.info("Генерация текста для видео-аватара через GigaChat...")
        with GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            verify_ssl_certs=False,
            scope='GIGACHAT_API_B2B',
            model='GigaChat-2-Pro'
        ) as giga:
            response = giga.chat(video_prompt)
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


def should_generate_video(answer: str, results_count: int = None) -> bool:
    """
    Проверяет, нужно ли генерировать видео на основе ответа и количества результатов.
    Генерируем видео, если есть данные (даже без координат).
    НЕ генерируем видео только если вообще нет данных по признаку.
    
    Args:
        answer: Ответ системы
        results_count: Количество найденных результатов (опционально)
        
    Returns:
        True если нужно генерировать видео, False если нет
    """
    # Если передан results_count и он больше 0 - генерируем видео
    if results_count is not None and results_count > 0:
        logger.info(f"Видео будет сгенерировано: найдено {results_count} результатов")
        return True
    
    answer_lower = answer.lower()
    
    # Фразы, которые ОДНОЗНАЧНО указывают на полное отсутствие данных (только если results_count не передан)
    # Эти фразы должны указывать на полное отсутствие результатов, а не на отсутствие части данных (например, координат)
    strict_no_data_phrases = [
        'к сожалению, по вашему запросу не найдено',
        'релевантных признаков в базе',
        'результатов не найдено',
        'ничего не найдено',
        'не найдено результатов',
        'данные не найдены в базе',
        'не найдено данных в базе',
        'отсутствуют данные в базе',
        'не найдено релевантных данных'
    ]
    
    # Проверяем наличие строгих фраз об отсутствии данных (только если не знаем results_count)
    for phrase in strict_no_data_phrases:
        if phrase in answer_lower:
            logger.info(f"Видео не будет сгенерировано: обнаружена строгая фраза об отсутствии данных '{phrase}'")
            return False
    
    # Если не нашли строгих фраз - генерируем видео (возможно, просто нет координат, но данные есть)
    # Но проверяем, нет ли явных признаков полного отсутствия данных
    weak_no_data_indicators = [
        'не найдено',
        'не найдены',
        'данных нет',
        'нет данных'
    ]
    
    # Если есть слабые индикаторы, но нет информации о количестве результатов - 
    # более консервативный подход: проверяем контекст
    weak_indicators_found = any(indicator in answer_lower for indicator in weak_no_data_indicators)
    
    if weak_indicators_found and results_count is None:
        # Проверяем, не говорит ли ответ о полном отсутствии данных
        # Если фраза стоит в начале ответа или в контексте "не найдено данных" - это признак отсутствия
        if any(answer_lower.startswith(phrase) or f' {phrase} ' in answer_lower or f' {phrase}.' in answer_lower 
               for phrase in ['не найдено', 'данных нет', 'нет данных']):
            logger.info("Видео не будет сгенерировано: обнаружены слабые индикаторы отсутствия данных")
            return False
    
    # По умолчанию генерируем видео, если не доказано обратное
    logger.info("Видео будет сгенерировано: данные найдены или не доказано обратное")
    return True


@method_decorator(csrf_exempt, name='dispatch') 
class HeyGenView(View):
    """API endpoint для подготовки текста для streaming видео через Interactive Avatar."""
    
    def post(self, request):
        """Подготовка текста для streaming видео (не генерирует видео, только подготавливает текст для Interactive Avatar)."""
        try:
            data = json.loads(request.body)
            full_answer = data.get('answer', '').strip()
            user_query = data.get('user_query', '').strip()
            has_coordinates = data.get('has_coordinates', False)
            results_count = data.get('results_count', None)  # Получаем количество результатов
            
            if not full_answer:
                return JsonResponse({
                    'error': 'Ответ не может быть пустым'
                }, status=400)
            
            # Проверяем, нужно ли генерировать видео (передаем results_count для более точной проверки)
            if not should_generate_video(full_answer, results_count=results_count):
                logger.info(f"Видео не будет сгенерировано: данные не найдены (results_count={results_count})")
                return JsonResponse({
                    'error': 'Видео не генерируется, так как данные не найдены',
                    'skip_video': True
                }, status=200)
            
            # Генерируем текст для видео через GigaChat (только подготовка текста для streaming)
            logger.info("Подготовка текста для streaming видео-аватара (Interactive Avatar)")
            video_text = prepare_video_text(full_answer, has_coordinates, user_query)
            
            # HeyGen Streaming API имеет ограничение на длину текста (обычно ~2000-2500 символов)
            # Обрезаем текст до разумного лимита, сохраняя целостность предложений
            MAX_TEXT_LENGTH = 2000  # Максимальная длина текста для HeyGen Streaming API
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
            
            # Возвращаем только подготовленный текст для streaming генерации
            # Само видео будет генерироваться через streaming API во frontend (Interactive Avatar)
            logger.info(f"Текст подготовлен для streaming генерации: {len(video_text)} символов")
            return JsonResponse({
                'video_text': video_text,
                'message': 'Текст подготовлен для streaming генерации через Interactive Avatar'
            })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Неверный формат JSON'
            }, status=400)
        except Exception as e:
            logger.error(f"Ошибка подготовки текста для streaming видео: {e}", exc_info=True)
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
        return JsonResponse(data)

