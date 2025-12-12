from opensearchpy import OpenSearch, helpers
import os
import json
import logging
from typing import List, Dict, Optional, Any, Tuple
import pandas as pd
from sentence_transformers import SentenceTransformer
from gigachat import GigaChat



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GigaChat будет инициализирован при использовании
GIGACHAT_CREDENTIALS = "MDE5YjA0YmYtMDNlMy03ZmVjLTgyN2EtNDI5OGFhYmM4YzlhOjVjMGJhYWRmLTQ4ZjktNGNkNC1iNjBkLTRhODVjYTY5Y2RmNQ=="

class OpenSearchManager:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        use_ssl: Optional[bool] = None,
        verify_certs: Optional[bool] = None,
        http_auth: Optional[Tuple[str, str]] = None,
        embedding_model: Optional[str] = None
    ):
        self.client = OpenSearch(
            host=host,
            port=port, 
            use_ssl=use_ssl, 
            verify_certs=verify_certs, 
            http_auth=http_auth,
            timeout = 30
        )
        # Инициализация модели для эмбеддингов (1024 измерения для SBERT от Сбера)
        model_name = embedding_model or "ai-forever/sbert_large_nlu_ru"
        logger.info(f"Загрузка модели эмбеддингов: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)

    def check_connection(self) -> bool:
        """Проверка подключения к OpenSearch."""
        try:
            info = self.client.info()
            logger.info(f"Подключено к OpenSearch: {info['version']['number']}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к OpenSearch: {e}")
            return False

    def create_index(self, name: str):
        if not self.client.indices.exists(index=name):
            print(f"Создаём индекс {name}...")
            mapping = {
                "settings": {
                    "index": {"knn": True, "number_of_shards": 1, "number_of_replicas": 0}
                },
                "mappings": {
                    "properties": {
                        "text": {"type": "text"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": 1024,
                            "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib"}
                        },
                        "location": {"type": "geo_point"},
                        "Corg": {"type": "float"},
                        "R0": {"type": "float"},
                        "depth": {"type": "float"},
                        "region": {"type": "keyword"},
                        "layer_name": {"type": "keyword"},
                        "source_file": {"type": "keyword"}
                    }
                }
            }
            self.client.indices.create(index=name, body=mapping)
            print("Индекс создан!")
        else:
            print("Индекс уже существует")

    def load_csv_to_index(
        self,
        csv_path: str,
        index_name: str,
        batch_size: int = 100,
        text_column: Optional[str] = None
    ) -> bool:
        """
        Загрузка данных из CSV файла в OpenSearch индекс.
        
        Args:
            csv_path: Путь к CSV файлу
            index_name: Имя индекса
            batch_size: Размер батча для индексации
            text_column: Имя колонки с текстом (если None, будет создан из всех текстовых колонок)
            
        Returns:
            True если успешно
        """
        if not self.client.indices.exists(index=index_name):
            logger.error(f"Индекс {index_name} не существует. Создайте его сначала.")
            return False
        
        logger.info(f"Загрузка CSV файла: {csv_path}")
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Загружено {len(df)} строк из CSV")
        except Exception as e:
            logger.error(f"Ошибка загрузки CSV: {e}")
            return False
        
        # Определение колонки с текстом
        if text_column and text_column in df.columns:
            text_col = text_column
        else:
            # Попытка найти текстовую колонку автоматически
            possible_text_cols = ['text', 'description', 'content', 'name', 'title']
            text_col = None
            for col in possible_text_cols:
                if col in df.columns:
                    text_col = col
                    break
            
            if not text_col:
                # Создаем текст из всех строковых колонок
                text_col = None
        
        actions = []
        processed = 0
        total_rows = len(df)
        
        logger.info(f"Начало индексации {total_rows} строк в индекс {index_name}")
        
        for idx, row in df.iterrows():
            try:
                # Создание текста
                if text_col:
                    text = str(row[text_col]) if pd.notna(row.get(text_col)) else ""
                else:
                    # Объединяем все строковые колонки в текст
                    text_parts = []
                    for col in df.columns:
                        if df[col].dtype == 'object' and pd.notna(row.get(col)):
                            text_parts.append(str(row[col]))
                    text = " ".join(text_parts) if text_parts else f"Запись {idx}"
                
                if not text.strip():
                    text = f"Запись {idx}"
                
                # Создание эмбеддинга
                embedding = self.embedding_model.encode(text).tolist()
                
                # Подготовка документа согласно маппингу индекса
                doc = {
                    "_index": index_name,
                    "_id": int(row.get('id', idx)) if pd.notna(row.get('id')) else idx,
                    "text": text,
                    "embedding": embedding,
                }
                
                # Добавление опциональных полей из маппинга
                if 'location' in df.columns and pd.notna(row.get('location')):
                    # location может быть в формате "lat,lon" или отдельными колонками lat/lon
                    doc["location"] = str(row['location'])
                elif 'lat' in df.columns and 'lon' in df.columns:
                    if pd.notna(row.get('lat')) and pd.notna(row.get('lon')):
                        doc["location"] = f"{row['lat']},{row['lon']}"
                
                # Числовые поля
                for field in ['Corg', 'R0', 'depth']:
                    if field in df.columns and pd.notna(row.get(field)):
                        try:
                            doc[field] = float(row[field])
                        except (ValueError, TypeError):
                            pass
                
                # Строковые поля (keyword)
                for field in ['region', 'layer_name', 'source_file']:
                    if field in df.columns and pd.notna(row.get(field)):
                        doc[field] = str(row[field])
                
                actions.append(doc)
                processed += 1
                
                # Батчинг
                if len(actions) >= batch_size:
                    helpers.bulk(self.client, actions, chunk_size=batch_size)
                    logger.info(f"Индексировано: {processed}/{total_rows}")
                    actions = []
                    
            except Exception as e:
                logger.error(f"Ошибка обработки строки {idx}: {e}")
                continue
        
        # Обработка оставшихся документов
        if actions:
            helpers.bulk(self.client, actions, chunk_size=batch_size)
            logger.info(f"Индексировано: {processed}/{total_rows}")
        
        logger.info(f"Индексация завершена: {processed}/{total_rows} строк")
        return True
    
    def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        """
        Получение статистики по индексу.
        
        Args:
            index_name: Имя индекса
            
        Returns:
            Словарь со статистикой
        """
        try:
            stats = self.client.indices.stats(index=index_name)
            return {
                "doc_count": stats["indices"][index_name]["total"]["docs"]["count"],
                "size": stats["indices"][index_name]["total"]["store"]["size_in_bytes"],
                "index_name": index_name
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    def list_indices(self) -> List[str]:
        """
        Получение списка всех индексов.
        
        Returns:
            Список имен индексов
        """
        try:
            indices = self.client.indices.get_alias("*")
            return list(indices.keys())
        except Exception as e:
            logger.error(f"Ошибка получения списка индексов: {e}")
            return []
    
    def get_documents(
        self,
        index_name: str,
        size: int = 10,
        from_: int = 0,
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение документов из индекса.
        
        Args:
            index_name: Имя индекса
            size: Количество документов
            from_: Смещение (для пагинации)
            fields: Список полей для возврата (None = все поля)
            
        Returns:
            Список документов
        """
        try:
            query = {
                "match_all": {}
            }
            
            body = {
                "query": query,
                "size": size,
                "from": from_
            }
            
            if fields:
                body["_source"] = fields
            
            response = self.client.search(index=index_name, body=body)
            
            documents = []
            for hit in response["hits"]["hits"]:
                doc = {
                    "_id": hit["_id"],
                    "_score": hit.get("_score"),
                    "_source": hit["_source"]
                }
                documents.append(doc)
            
            return documents
        except Exception as e:
            logger.error(f"Ошибка получения документов: {e}")
            return []
    
    def get_sample_documents(self, index_name: str, count: int = 5) -> None:
        """
        Вывод примеров документов из индекса.
        
        Args:
            index_name: Имя индекса
            count: Количество примеров
        """
        print(f"\n{'='*80}")
        print(f"Примеры документов из индекса '{index_name}' (первые {count}):")
        print('='*80)
        
        docs = self.get_documents(index_name, size=count)
        
        if not docs:
            print("Документы не найдены или индекс пуст")
            return
        
        for i, doc in enumerate(docs, 1):
            print(f"\n--- Документ {i} (ID: {doc['_id']}) ---")
            source = doc["_source"]
            
            # Выводим основные поля
            if "text" in source:
                text_preview = source["text"][:200] + "..." if len(source["text"]) > 200 else source["text"]
                print(f"Текст: {text_preview}")
            
            # Выводим числовые поля
            for field in ["Corg", "R0", "depth"]:
                if field in source:
                    print(f"{field}: {source[field]}")
            
            # Выводим строковые поля
            for field in ["region", "layer_name", "source_file"]:
                if field in source:
                    print(f"{field}: {source[field]}")
            
            # Выводим location если есть
            if "location" in source:
                print(f"location: {source['location']}")
            
            print()
    
    def get_index_mapping(self, index_name: str) -> Dict[str, Any]:
        """
        Получение маппинга индекса.
        
        Args:
            index_name: Имя индекса
            
        Returns:
            Маппинг индекса
        """
        try:
            mapping = self.client.indices.get_mapping(index=index_name)
            return mapping[index_name]["mappings"]
        except Exception as e:
            logger.error(f"Ошибка получения маппинга: {e}")
            return {}
    
    def print_index_info(self, index_name: str) -> None:
        """
        Вывод полной информации об индексе.
        
        Args:
            index_name: Имя индекса
        """
        print(f"\n{'='*80}")
        print(f"Информация об индексе: {index_name}")
        print('='*80)
        
        # Проверка существования
        if not self.client.indices.exists(index=index_name):
            print(f"Индекс '{index_name}' не существует")
            return
        
        # Статистика
        stats = self.get_index_stats(index_name)
        if stats:
            print(f"\nСтатистика:")
            print(f"  Количество документов: {stats.get('doc_count', 0)}")
            print(f"  Размер: {stats.get('size', 0) / 1024 / 1024:.2f} MB")
        
        # Маппинг
        mapping = self.get_index_mapping(index_name)
        if mapping:
            print(f"\nПоля индекса:")
            properties = mapping.get("properties", {})
            for field_name, field_type in properties.items():
                field_info = field_type.get("type", "unknown")
                if "dimension" in field_type:
                    field_info += f" (dimension: {field_type['dimension']})"
                print(f"  - {field_name}: {field_info}")
        
        # Примеры документов
        self.get_sample_documents(index_name, count=3)


if __name__ == "__main__":
    # Инициализация для HTTPS
    manager = OpenSearchManager(
        host="localhost",
        port=9200,  # Или 443 для стандартного HTTPS
        use_ssl=True,  # Включить HTTPS
        verify_certs=False,  # Проверять сертификаты
        http_auth=("admin", "Rodion1killer"),  # Если требуется аутентификация
    )
    
    # Проверка подключения
    if not manager.check_connection():
        print("Не удалось подключиться к OpenSearch")
        exit(1)
    
    index_name = "rag_neft"

    manager.create_index(name=index_name)
    
    # Загрузка данных из CSV
    csv_path = "/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/ЦК(25.06.25)/pars_test.csv"
    if os.path.exists(csv_path):
        logger.info(f"Загрузка данных из {csv_path}...")
        manager.load_csv_to_index(
            csv_path=csv_path,
            index_name=index_name,
            batch_size=100
        )
        logger.info("Загрузка завершена!")
    else:
        logger.warning(f"Файл {csv_path} не найден. Проверьте путь к файлу.")

    # Просмотр данных в OpenSearch
    # Список всех индексов
    print("\n" + "="*80)
    print("СПИСОК ИНДЕКСОВ В OPENSEARCH:")
    print("="*80)
    indices = manager.list_indices()
    if indices:
        for idx in indices:
            print(f"  - {idx}")
    else:
        print("  Индексы не найдены")
    
    # Информация об индексе
    if manager.client.indices.exists(index=index_name):
        manager.print_index_info(index_name)
    else:
        print(f"\nИндекс '{index_name}' не существует")
    
    # Получение большего количества документов
    print(f"\n{'='*80}")
    print(f"ПОЛУЧЕНИЕ ДОКУМЕНТОВ ИЗ ИНДЕКСА '{index_name}'")
    print('='*80)
    docs = manager.get_documents(index_name, size=10)
    print(f"\nНайдено документов: {len(docs)}")
    
    if docs:
        print(f"\nПервые {min(5, len(docs))} документов:")
        for i, doc in enumerate(docs[:5], 1):
            print(f"\n{i}. ID: {doc['_id']}")
            source = doc.get('_source', {})
            # Показываем только ключевые поля
            for key in ['text', 'Corg', 'R0', 'depth', 'region', 'layer_name']:
                if key in source:
                    value = source[key]
                    if key == 'text' and isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    print(f"   {key}: {value}")