"""
Скрипт для генерации описаний всех признаков из rag_layers_export.json через GigaChat.
Генерирует JSON файл с описаниями и эмбеддингами для импорта в OpenSearch.

Использование:
    python generate_feature_descriptions.py

Требования:
    - Установленный gigachat: pip install gigachat>=0.1.0
    - Установленный pandas: pip install pandas>=2.0.0
    - Установленный sentence-transformers: pip install sentence-transformers>=2.2.0
    - Для Excel файла: pip install openpyxl (опционально)
    - Переменная окружения GIGACHAT_CREDENTIALS или учетные данные в коде

Особенности:
    - Автоматическое сохранение промежуточных результатов каждые 10 признаков
    - Возможность возобновления обработки с определенного индекса (параметр start_from)
    - Задержка между запросами для избежания rate limiting
    - Обработка ошибок и повторные попытки
    - Генерация эмбеддингов для каждого описания

Выходные файлы:
    - opensearch_export/feature_descriptions_export.json - JSON для импорта в OpenSearch
    - opensearch_export/feature_descriptions.csv - CSV файл (опционально)
    - opensearch_export/feature_descriptions.xlsx - Excel файл (опционально, если установлен openpyxl)
"""

import json
import pandas as pd
import logging
from typing import Dict, List, Any
from gigachat import GigaChat
from sentence_transformers import SentenceTransformer
import time
import os
import argparse
import numpy as np

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Учетные данные GigaChat
GIGACHAT_CREDENTIALS = os.environ.get(
    'GIGACHAT_CREDENTIALS',
    "MDE5OWUyNTAtNGNhZS03ZDdjLTg2ZmMtZjM5NDE0ZGFhNjUzOmYzMTk3ZWUyLTBlNTYtNDUzNy04ZWViLTUyZWU4ZjAyZGMzZA=="
)

# Модель для генерации эмбеддингов
EMBEDDING_MODEL_NAME = "ai-forever/sbert_large_nlu_ru"

# Промпт для генерации описания признака
FEATURE_DESCRIPTION_PROMPT = """Ты - эксперт по геологическим признакам и нефтегазовой геологии Каспийского моря.

Название признака: "{feature_name}"
Тип данных: {feature_type}

Твоя задача - создать подробное описание этого геологического признака:
1. Что означает этот признак в контексте нефтегазовой геологии
2. Его назначение и применение
3. Единицы измерения (если применимо)
4. Типичные диапазоны значений (если известны)
5. Как этот признак используется в анализе геологических данных Каспийского моря

Описание должно быть информативным, профессиональным и содержать ключевые термины, которые помогут понять значение признака.

Верни только описание без дополнительных комментариев."""


def load_features_from_json(json_path: str) -> Dict[str, Dict]:
    """
    Загружает признаки из JSON файла.
    
    Args:
        json_path: Путь к файлу rag_layers_export.json
        
    Returns:
        Словарь с признаками и их типами
    """
    logger.info(f"Загрузка признаков из {json_path}...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    mappings = data.get('mappings', {})
    properties = mappings.get('properties', {})
    
    features = {}
    for feature_name, feature_info in properties.items():
        # Определяем тип данных
        feature_type = feature_info.get('type', 'unknown')
        if 'fields' in feature_info:
            # Если есть keyword поле, это текстовое поле
            feature_type = f"{feature_type} (keyword)"
        
        features[feature_name] = {
            'type': feature_type,
            'full_info': feature_info
        }
    
    logger.info(f"Загружено {len(features)} признаков")
    return features


def generate_description_with_gigachat(feature_name: str, feature_type: str, max_retries: int = 3) -> str:
    """
    Генерирует описание признака через GigaChat.
    
    Args:
        feature_name: Название признака
        feature_type: Тип данных признака
        max_retries: Максимальное количество попыток
        
    Returns:
        Описание признака
    """
    prompt = FEATURE_DESCRIPTION_PROMPT.format(
        feature_name=feature_name,
        feature_type=feature_type
    )
    
    for attempt in range(max_retries):
        try:
            with GigaChat(
                credentials=GIGACHAT_CREDENTIALS,
                verify_ssl_certs=False,
                scope='GIGACHAT_API_B2B',
                model='GigaChat-2-Pro'
            ) as giga:
                response = giga.chat(prompt)
                description = response.choices[0].message.content.strip()
                logger.info(f"✓ Описание для '{feature_name}' сгенерировано")
                return description
                
        except Exception as e:
            logger.warning(f"Попытка {attempt + 1}/{max_retries} для '{feature_name}' не удалась: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Экспоненциальная задержка
            else:
                logger.error(f"Не удалось сгенерировать описание для '{feature_name}' после {max_retries} попыток")
                return f"Ошибка генерации: {str(e)}"


def generate_embedding(text: str, embedding_model: SentenceTransformer) -> List[float]:
    """
    Генерирует эмбеддинг для текста.
    
    Args:
        text: Текст для векторизации
        embedding_model: Модель для генерации эмбеддингов
        
    Returns:
        Список чисел (вектор эмбеддинга)
    """
    try:
        embedding = embedding_model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Ошибка генерации эмбеддинга: {e}")
        return []


def create_opensearch_mapping() -> Dict[str, Any]:
    """
    Создает mapping для индекса OpenSearch с описаниями признаков.
    
    Returns:
        Словарь с mapping для OpenSearch
    """
    return {
        "properties": {
            "text": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "embedding": {
                "type": "knn_vector",
                "dimension": 1024,  # Размерность для ai-forever/sbert_large_nlu_ru
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib"
                }
            }
        }
    }


def process_all_features(
    features: Dict[str, Dict],
    output_json: str = "feature_descriptions_export.json",
    output_csv: str = "feature_descriptions.csv",
    output_excel: str = "feature_descriptions.xlsx",
    delay_between_requests: float = 1.0,
    start_from: int = 0,
    save_csv: bool = True,
    save_excel: bool = False
):
    """
    Обрабатывает все признаки и генерирует описания с эмбеддингами.
    
    Args:
        features: Словарь с признаками
        output_json: Путь к выходному JSON файлу для OpenSearch
        output_csv: Путь к выходному CSV файлу (опционально)
        output_excel: Путь к выходному Excel файлу (опционально)
        delay_between_requests: Задержка между запросами (секунды)
        start_from: Начать обработку с указанного индекса (для возобновления)
        save_csv: Сохранять ли CSV файл
        save_excel: Сохранять ли Excel файл
    """
    # Инициализация модели эмбеддингов
    logger.info(f"Загрузка модели эмбеддингов: {EMBEDDING_MODEL_NAME}...")
    try:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("✓ Модель эмбеддингов загружена")
    except Exception as e:
        logger.error(f"Ошибка загрузки модели эмбеддингов: {e}")
        raise
    
    # Загружаем существующие результаты, если файл существует
    documents = []
    csv_results = []
    
    if start_from > 0 and os.path.exists(output_json):
        try:
            with open(output_json, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                documents = existing_data.get('documents', [])
                logger.info(f"Загружено {len(documents)} существующих документов из {output_json}")
        except Exception as e:
            logger.warning(f"Не удалось загрузить существующие результаты: {e}")
            documents = []
    
    if start_from > 0 and save_csv and os.path.exists(output_csv):
        try:
            existing_df = pd.read_csv(output_csv, encoding='utf-8-sig')
            csv_results = existing_df.to_dict('records')
            logger.info(f"Загружено {len(csv_results)} существующих результатов из {output_csv}")
        except Exception as e:
            logger.warning(f"Не удалось загрузить существующие CSV результаты: {e}")
            csv_results = []
    
    total_features = len(features)
    logger.info(f"Начинаю обработку {total_features} признаков (начиная с индекса {start_from})...")
    
    feature_list = list(features.items())
    
    for idx, (feature_name, feature_info) in enumerate(feature_list):
        if idx < start_from:
            continue
            
        logger.info(f"[{idx + 1}/{total_features}] Обработка признака: '{feature_name}'")
        
        feature_type = feature_info['type']
        
        # Генерация описания через GigaChat
        description = generate_description_with_gigachat(feature_name, feature_type)
        
        # Формируем полный текст для эмбеддинга (как в feature_descriptions)
        full_text = f"Признак: {feature_name}\nОписание: {description}"
        
        # Генерация эмбеддинга
        logger.info(f"  Генерация эмбеддинга для '{feature_name}'...")
        embedding = generate_embedding(description, embedding_model)  # Используем только описание для эмбеддинга
        
        # Создаем документ для OpenSearch
        document = {
            "_id": str(idx),
            "_source": {
                "text": full_text,
                "embedding": embedding
            }
        }
        documents.append(document)
        
        # Для CSV/Excel
        if save_csv or save_excel:
            csv_results.append({
                'Название признака': feature_name,
                'Тип данных': feature_type,
                'Описание': description
            })
        
        # Сохраняем промежуточные результаты каждые 10 признаков
        if (idx + 1) % 10 == 0:
            # Сохраняем JSON
            export_data = {
                "index_name": "feature_descriptions",
                "mappings": create_opensearch_mapping(),
                "settings": {},
                "documents": documents,
                "total_documents": len(documents)
            }
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Промежуточное сохранение JSON: обработано {len(documents)} признаков")
            
            # Сохраняем CSV если нужно
            if save_csv:
                df = pd.DataFrame(csv_results)
                df.to_csv(output_csv, index=False, encoding='utf-8-sig')
                logger.info(f"Промежуточное сохранение CSV: обработано {len(csv_results)} признаков")
        
        # Задержка между запросами
        if idx < total_features - 1:
            time.sleep(delay_between_requests)
    
    # Финальное сохранение JSON
    logger.info(f"Сохранение результатов в {output_json}...")
    export_data = {
        "index_name": "feature_descriptions",
        "mappings": create_opensearch_mapping(),
        "settings": {},
        "documents": documents,
        "total_documents": len(documents)
    }
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    logger.info(f"✓ JSON файл сохранен: {output_json}")
    logger.info(f"  Всего документов: {len(documents)}")
    
    # Сохранение CSV (если нужно)
    if save_csv:
        df = pd.DataFrame(csv_results)
        logger.info(f"Сохранение результатов в {output_csv}...")
        df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        logger.info(f"✓ CSV файл сохранен: {output_csv}")
    
    # Сохранение в Excel (если нужно и установлен openpyxl)
    if save_excel:
        try:
            import openpyxl
            logger.info(f"Сохранение результатов в {output_excel}...")
            df = pd.DataFrame(csv_results)
            with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Описания признаков')
                
                # Автоматическая настройка ширины колонок
                worksheet = writer.sheets['Описания признаков']
                worksheet.column_dimensions['A'].width = 30  # Название признака
                worksheet.column_dimensions['B'].width = 20  # Тип данных
                worksheet.column_dimensions['C'].width = 80  # Описание
                
            logger.info(f"✓ Excel файл сохранен: {output_excel}")
        except ImportError:
            logger.warning("openpyxl не установлен. Excel файл не будет создан.")
            logger.info("Для создания Excel файла установите: pip install openpyxl")
    
    logger.info(f"Всего обработано: {len(documents)} признаков")


def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(
        description='Генерация описаний всех признаков из rag_layers_export.json через GigaChat'
    )
    parser.add_argument(
        '--start-from',
        type=int,
        default=0,
        help='Начать обработку с указанного индекса (для возобновления)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Задержка между запросами в секундах (по умолчанию: 1.0)'
    )
    parser.add_argument(
        '--json-path',
        type=str,
        default=None,
        help='Путь к файлу rag_layers_export.json (по умолчанию: opensearch_export/rag_layers_export.json)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Директория для сохранения результатов (по умолчанию: opensearch_export)'
    )
    parser.add_argument(
        '--save-csv',
        action='store_true',
        help='Сохранять CSV файл (опционально)'
    )
    parser.add_argument(
        '--save-excel',
        action='store_true',
        help='Сохранять Excel файл (опционально, требует openpyxl)'
    )
    
    args = parser.parse_args()
    
    # Пути к файлам
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if args.json_path:
        json_path = args.json_path
    else:
        json_path = os.path.join(script_dir, 'opensearch_export', 'rag_layers_export.json')
    
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.join(script_dir, 'opensearch_export')
    
    os.makedirs(output_dir, exist_ok=True)
    
    output_json = os.path.join(output_dir, 'feature_descriptions_export.json')
    output_csv = os.path.join(output_dir, 'feature_descriptions.csv')
    output_excel = os.path.join(output_dir, 'feature_descriptions.xlsx')
    
    # Проверка существования JSON файла
    if not os.path.exists(json_path):
        logger.error(f"Файл не найден: {json_path}")
        return
    
    # Загрузка признаков
    features = load_features_from_json(json_path)
    
    if not features:
        logger.error("Не удалось загрузить признаки из JSON файла")
        return
    
    logger.info(f"Всего признаков для обработки: {len(features)}")
    logger.info(f"Начинаю с индекса: {args.start_from}")
    logger.info(f"Задержка между запросами: {args.delay} сек")
    logger.info(f"Сохранять CSV: {args.save_csv}")
    logger.info(f"Сохранять Excel: {args.save_excel}")
    
    # Обработка всех признаков
    try:
        process_all_features(
            features=features,
            output_json=output_json,
            output_csv=output_csv,
            output_excel=output_excel,
            delay_between_requests=args.delay,
            start_from=args.start_from,
            save_csv=args.save_csv,
            save_excel=args.save_excel
        )
        logger.info("✓ Обработка завершена успешно!")
        logger.info(f"✓ JSON файл для OpenSearch: {output_json}")
        
    except KeyboardInterrupt:
        logger.warning("Обработка прервана пользователем")
        logger.info(f"Промежуточные результаты сохранены в {output_json}")
        logger.info(f"Для возобновления используйте: --start-from <номер_последнего_обработанного_признака>")
    except Exception as e:
        logger.error(f"Ошибка при обработке: {e}", exc_info=True)


if __name__ == "__main__":
    main()

