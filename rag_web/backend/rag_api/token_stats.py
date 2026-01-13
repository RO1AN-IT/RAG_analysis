"""
Модуль для сбора и сохранения статистики использования токенов GigaChat API.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional
from collections import defaultdict
import threading

# Блокировка для потокобезопасности
_stats_lock = threading.Lock()

# Хранилище статистики в памяти
_token_stats: Dict[str, Dict] = defaultdict(lambda: {
    'model': '',
    'price_per_1k': 0.0,
    'requests_count': 0,
    'total_tokens': 0,
    'prompt_tokens': 0,
    'completion_tokens': 0
})

# Цены за 1K токенов для разных моделей (в рублях)
MODEL_PRICES = {
    'GigaChat-Max': 1.95,
    'GigaChat-Pro': 1.50,
    'GigaChat-2-Pro': 1.50,
    'GigaChat:light': 0.20,
    'GigaChat': 1.50,  # По умолчанию
}

# Путь к файлу статистики
STATS_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    'gigachat_token_stats.txt'
)


def record_token_usage(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: Optional[int] = None
):
    """
    Запись использования токенов для модели.
    
    Args:
        model: Название модели (например, 'GigaChat:light')
        prompt_tokens: Количество входных токенов
        completion_tokens: Количество выходных токенов
        total_tokens: Общее количество токенов (если не указано, вычисляется)
    """
    with _stats_lock:
        model_key = model
        
        if model_key not in _token_stats:
            _token_stats[model_key] = {
                'model': model,
                'price_per_1k': MODEL_PRICES.get(model, MODEL_PRICES['GigaChat']),
                'requests_count': 0,
                'total_tokens': 0,
                'prompt_tokens': 0,
                'completion_tokens': 0
            }
        
        stats = _token_stats[model_key]
        stats['model'] = model
        stats['price_per_1k'] = MODEL_PRICES.get(model, MODEL_PRICES['GigaChat'])
        stats['requests_count'] += 1
        stats['prompt_tokens'] += prompt_tokens
        stats['completion_tokens'] += completion_tokens
        
        if total_tokens is not None:
            stats['total_tokens'] += total_tokens
        else:
            stats['total_tokens'] += (prompt_tokens + completion_tokens)


def record_from_response(model: str, response):
    """
    Запись статистики из объекта ответа GigaChat.
    
    Args:
        model: Название модели
        response: Объект ответа от GigaChat API
    """
    try:
        # Пытаемся получить информацию о токенах из response
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        
        if hasattr(response, 'usage'):
            usage = response.usage
            if hasattr(usage, 'prompt_tokens'):
                prompt_tokens = usage.prompt_tokens
            if hasattr(usage, 'completion_tokens'):
                completion_tokens = usage.completion_tokens
            if hasattr(usage, 'total_tokens'):
                total_tokens = usage.total_tokens
        
        # Если usage нет, пытаемся получить из других мест
        elif hasattr(response, 'choices') and response.choices:
            # Иногда информация о токенах может быть в других полях
            pass
        
        if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
            record_token_usage(model, prompt_tokens, completion_tokens, total_tokens)
    except Exception as e:
        # Если не удалось получить статистику, просто пропускаем
        pass


def format_number(num: int) -> str:
    """Форматирование числа с разделителями тысяч."""
    return f"{num:,}".replace(',', ' ')


def save_stats_to_file():
    """Сохранение статистики в текстовый файл."""
    with _stats_lock:
        if not _token_stats:
            # Если статистики нет, создаем пустой файл
            with open(STATS_FILE_PATH, 'w', encoding='utf-8') as f:
                f.write("📈 Статистика использования токенов GigaChat API\n")
                f.write(f"Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 53 + "\n\n")
                f.write("Статистика пока отсутствует.\n")
            return
        
        # Сортируем модели по названию
        sorted_models = sorted(_token_stats.items())
        
        # Вычисляем общую статистику
        total_requests = sum(stats['requests_count'] for stats in _token_stats.values())
        total_tokens_all = sum(stats['total_tokens'] for stats in _token_stats.values())
        total_cost_all = sum(
            (stats['total_tokens'] / 1000) * stats['price_per_1k']
            for stats in _token_stats.values()
        )
        
        with open(STATS_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("📈 Статистика использования токенов GigaChat API\n")
            f.write(f"Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 53 + "\n\n")
            
            # Статистика по каждой модели
            for model_key, stats in sorted_models:
                model_name = stats['model']
                price = stats['price_per_1k']
                requests = stats['requests_count']
                total_tokens = stats['total_tokens']
                prompt_tokens = stats['prompt_tokens']
                completion_tokens = stats['completion_tokens']
                
                avg_tokens = total_tokens / requests if requests > 0 else 0
                avg_prompt = prompt_tokens / requests if requests > 0 else 0
                avg_completion = completion_tokens / requests if requests > 0 else 0
                
                total_cost = (total_tokens / 1000) * price
                avg_cost = total_cost / requests if requests > 0 else 0
                
                f.write(f"🤖 Модель: {model_name}\n")
                f.write(f"   Цена за 1K токенов: {price:.2f} ₽\n")
                f.write(f"   Количество запросов: {requests}\n")
                f.write(f"   Всего токенов: {format_number(total_tokens)}\n")
                f.write(f"     - Входных (prompt): {format_number(prompt_tokens)}\n")
                f.write(f"     - Выходных (completion): {format_number(completion_tokens)}\n")
                f.write(f"   Среднее токенов на запрос: {avg_tokens:.1f}\n")
                f.write(f"     - Входных: {avg_prompt:.1f}\n")
                f.write(f"     - Выходных: {avg_completion:.1f}\n")
                f.write(f"   💰 Общая стоимость: {total_cost:.4f} ₽\n")
                f.write(f"   💰 Средняя стоимость запроса: {avg_cost:.4f} ₽\n")
                f.write("\n")
            
            # Общая статистика
            f.write("=" * 53 + "\n")
            f.write("📊 ОБЩАЯ СТАТИСТИКА\n")
            f.write("=" * 53 + "\n")
            f.write(f"Всего запросов: {total_requests}\n")
            f.write(f"Всего токенов: {format_number(total_tokens_all)}\n")
            f.write(f"💰 Общая стоимость всех тестов: {total_cost_all:.4f} ₽\n")
            f.write("=" * 53 + "\n")


def get_stats() -> Dict[str, Dict]:
    """Получение текущей статистики."""
    with _stats_lock:
        return dict(_token_stats)


def reset_stats():
    """Сброс статистики."""
    with _stats_lock:
        _token_stats.clear()


def clear_stats_file():
    """Очистка файла статистики и сброс в памяти."""
    reset_stats()
    with open(STATS_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write("📈 Статистика использования токенов GigaChat API\n")
        f.write(f"Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 53 + "\n\n")
        f.write("Статистика обнулена.\n")

