"""
Скрипт для индексации данных из CSV файла в OpenSearch.

Использует векторные эмбеддинги для семантического поиска.
"""

import os
import logging
import pandas as pd
from opensearch_test import OpenSearchManager
from opensearchpy import helpers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def index_csv_to_opensearch(
    csv_path: str,
    index_name: str,
    opensearch_host: str = "localhost",
    opensearch_port: int = 9200,
    opensearch_use_ssl: bool = False,
    opensearch_verify_certs: bool = False,
    opensearch_auth: tuple = None,
    batch_size: int = 100,
    text_column: str = None,
    embedding_model: str = "ai-forever/sbert_large_nlu_ru",
    create_index_if_not_exists: bool = True
):
    """
    Индексация данных из CSV файла в OpenSearch.
    
    Args:
        csv_path: Путь к CSV файлу
        index_name: Имя индекса в OpenSearch
        opensearch_host: Хост OpenSearch
        opensearch_port: Порт OpenSearch
        opensearch_use_ssl: Использовать SSL
        opensearch_verify_certs: Проверять сертификаты
        opensearch_auth: Учетные данные (username, password)
        batch_size: Размер батча для индексации
        text_column: Имя колонки с текстом (если None, будет создан из всех текстовых колонок)
        embedding_model: Модель для эмбеддингов
        create_index_if_not_exists: Создавать индекс, если его нет
        
    Returns:
        True если успешно, False в противном случае
    """
    
    # Проверка существования CSV файла
    if not os.path.exists(csv_path):
        logger.error(f"CSV файл не найден: {csv_path}")
        return False
    
    # Инициализация OpenSearchManager
    logger.info(f"Подключение к OpenSearch: {opensearch_host}:{opensearch_port}")
    manager = OpenSearchManager(
        host=opensearch_host,
        port=opensearch_port,
        use_ssl=opensearch_use_ssl,
        verify_certs=opensearch_verify_certs,
        http_auth=opensearch_auth,
        embedding_model=embedding_model
    )
    
    # Проверка подключения
    if not manager.check_connection():
        logger.error("Не удалось подключиться к OpenSearch")
        return False
    
    # Создание индекса, если его нет
    if create_index_if_not_exists:
        logger.info(f"Проверка существования индекса: {index_name}")
        manager.create_index(name=index_name)
    
    # Проверка существования индекса после создания
    if not manager.client.indices.exists(index=index_name):
        logger.error(f"Индекс {index_name} не существует и не был создан")
        return False
    
    # Загрузка CSV файла
    logger.info(f"Загрузка CSV файла: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Загружено {len(df)} строк из CSV")
        logger.info(f"Колонки: {list(df.columns)[:10]}...")  # Первые 10 колонок
    except Exception as e:
        logger.error(f"Ошибка загрузки CSV: {e}")
        return False
    
    # Определение колонки с текстом
    if text_column and text_column in df.columns:
        text_col = text_column
        logger.info(f"Используется указанная текстовая колонка: {text_col}")
    else:
        # Попытка найти текстовую колонку автоматически
        possible_text_cols = ['text', 'description', 'content', 'name', 'title', 'layer_name']
        text_col = None
        for col in possible_text_cols:
            if col in df.columns:
                text_col = col
                logger.info(f"Автоматически найдена текстовая колонка: {text_col}")
                break
        
        if not text_col:
            logger.info("Текстовая колонка не найдена, будет создана из всех строковых колонок")
            text_col = None
    
    # Подготовка данных для индексации
    actions = []
    processed = 0
    total_rows = len(df)
    errors = 0
    
    logger.info(f"Начало индексации {total_rows} строк в индекс {index_name}")
    logger.info(f"Размер батча: {batch_size}")
    
    for idx, row in df.iterrows():
        try:
            # Создание текста для эмбеддинга
            if text_col:
                text = str(row[text_col]) if pd.notna(row.get(text_col)) else ""
            else:
                # Объединяем все строковые колонки в текст
                text_parts = []
                for col in df.columns:
                    if df[col].dtype == 'object' and pd.notna(row.get(col)):
                        value = str(row[col]).strip()
                        if value and value not in ['nan', 'None', 'null', 'NULL', '']:
                            text_parts.append(value)
                text = " ".join(text_parts) if text_parts else f"Запись {idx}"
            
            if not text.strip():
                text = f"Запись {idx}"
            
            # Создание эмбеддинга
            embedding = manager.embedding_model.encode(text).tolist()
            
            # Подготовка документа
            doc = {
                "_index": index_name,
                "_id": int(row.get('id', idx)) if pd.notna(row.get('id')) else idx,
                "text": text,
                "embedding": embedding,
            }
            
            # Добавление всех полей из CSV (кроме тех, что уже добавлены)
            for col in df.columns:
                if col not in ['id', 'text', 'embedding']:
                    value = row.get(col)
                    if pd.notna(value):
                        # Преобразование типов
                        if df[col].dtype in ['int64', 'int32']:
                            try:
                                doc[col] = int(value)
                            except:
                                doc[col] = str(value)
                        elif df[col].dtype in ['float64', 'float32']:
                            try:
                                doc[col] = float(value)
                            except:
                                doc[col] = str(value)
                        else:
                            doc[col] = str(value)
            
            # Специальная обработка координат для geo_point
            if 'lon' in df.columns and 'lat' in df.columns:
                lon = row.get('lon')
                lat = row.get('lat')
                if pd.notna(lon) and pd.notna(lat):
                    try:
                        # Обработка массивов координат
                        lon_str = str(lon).strip()
                        lat_str = str(lat).strip()
                        
                        # Если координаты в формате массива
                        if lon_str.startswith('['):
                            import ast
                            lon_array = ast.literal_eval(lon_str)
                            lon_val = lon_array[0] if isinstance(lon_array, list) and len(lon_array) > 0 else None
                        else:
                            lon_val = float(lon_str) if lon_str not in ['nan', 'None'] else None
                        
                        if lat_str.startswith('['):
                            import ast
                            lat_array = ast.literal_eval(lat_str)
                            lat_val = lat_array[-1] if isinstance(lat_array, list) and len(lat_array) > 0 else None
                        else:
                            lat_val = float(lat_str) if lat_str not in ['nan', 'None'] else None
                        
                        if lon_val is not None and lat_val is not None:
                            doc["location"] = f"{lat_val},{lon_val}"  # OpenSearch использует lat,lon
                    except Exception as e:
                        logger.debug(f"Ошибка обработки координат для строки {idx}: {e}")
            
            actions.append(doc)
            processed += 1
            
            # Батчинг - отправка батча в OpenSearch
            if len(actions) >= batch_size:
                try:
                    helpers.bulk(manager.client, actions, chunk_size=batch_size)
                    logger.info(f"Индексировано: {processed}/{total_rows} ({processed*100//total_rows}%)")
                    actions = []
                except Exception as e:
                    logger.error(f"Ошибка при индексации батча: {e}")
                    errors += len(actions)
                    actions = []
                    
        except Exception as e:
            logger.error(f"Ошибка обработки строки {idx}: {e}")
            errors += 1
            continue
    
    # Обработка оставшихся документов
    if actions:
        try:
            helpers.bulk(manager.client, actions, chunk_size=batch_size)
            logger.info(f"Индексировано: {processed}/{total_rows}")
        except Exception as e:
            logger.error(f"Ошибка при индексации последнего батча: {e}")
            errors += len(actions)
    
    # Итоговая статистика
    logger.info("="*80)
    logger.info("ИНДЕКСАЦИЯ ЗАВЕРШЕНА")
    logger.info("="*80)
    logger.info(f"Всего строк в CSV: {total_rows}")
    logger.info(f"Успешно обработано: {processed}")
    logger.info(f"Ошибок: {errors}")
    logger.info(f"Успешность: {(processed-errors)*100/max(processed,1):.1f}%")
    logger.info("="*80)
    
    # Проверка количества документов в индексе
    try:
        count_response = manager.client.count(index=index_name)
        indexed_count = count_response['count']
        logger.info(f"Документов в индексе {index_name}: {indexed_count}")
    except Exception as e:
        logger.warning(f"Не удалось получить количество документов в индексе: {e}")
    
    return errors == 0


if __name__ == "__main__":
    # Конфигурация
    CSV_PATH = "/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/features_database.csv"
    INDEX_NAME = "rag_descriptions"
    
    # Конфигурация OpenSearch
    OPENSEARCH_HOST = "localhost"
    OPENSEARCH_PORT = 9200
    OPENSEARCH_USE_SSL = True
    OPENSEARCH_VERIFY_CERTS = False
    OPENSEARCH_AUTH = ("admin", "Rodion1killer")  # Замените на свои данные
    
    # Параметры индексации
    BATCH_SIZE = 100  # Размер батча (можно увеличить для ускорения)
    TEXT_COLUMN = None  # None = автоматический выбор или создание из всех колонок
    EMBEDDING_MODEL = "ai-forever/sbert_large_nlu_ru"
    
    logger.info("="*80)
    logger.info("ИНДЕКСАЦИЯ CSV В OPENSEARCH")
    logger.info("="*80)
    logger.info(f"CSV файл: {CSV_PATH}")
    logger.info(f"Индекс: {INDEX_NAME}")
    logger.info(f"OpenSearch: {OPENSEARCH_HOST}:{OPENSEARCH_PORT}")
    logger.info("="*80)
    
    # Проверка существования CSV файла
    if not os.path.exists(CSV_PATH):
        logger.error(f"CSV файл не найден: {CSV_PATH}")
        logger.error("Проверьте путь к файлу")
        exit(1)
    
    # Запуск индексации
    success = index_csv_to_opensearch(
        csv_path=CSV_PATH,
        index_name=INDEX_NAME,
        opensearch_host=OPENSEARCH_HOST,
        opensearch_port=OPENSEARCH_PORT,
        opensearch_use_ssl=OPENSEARCH_USE_SSL,
        opensearch_verify_certs=OPENSEARCH_VERIFY_CERTS,
        opensearch_auth=OPENSEARCH_AUTH,
        batch_size=BATCH_SIZE,
        text_column=TEXT_COLUMN,
        embedding_model=EMBEDDING_MODEL,
        create_index_if_not_exists=True
    )
    
    if success:
        logger.info("\n✅ Индексация завершена успешно!")
    else:
        logger.error("\n❌ Индексация завершена с ошибками. Проверьте логи выше.")

