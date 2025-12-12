"""
Модуль для работы с OpenSearch в RAG системе.

Функциональность:
- Подключение к OpenSearch
- Создание индексов с векторными полями
- Индексация данных с эмбеддингами
- Семантический поиск
- Интеграция с LangChain
- Управление индексами
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
import pandas as pd
import numpy as np

# Настройка логирования сначала
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из .env файла
def load_env_file(env_path: str = ".env"):
    """Загрузка переменных окружения из .env файла."""
    env_file = Path(env_path)
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                # Парсим KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    # Устанавливаем только если не установлено
                    if key and key not in os.environ:
                        os.environ[key] = value

# Автоматическая загрузка .env при импорте модуля
load_env_file()

# Импорты с обработкой отсутствующих модулей
try:
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from opensearchpy.helpers import bulk
except ImportError:
    logger.error("opensearchpy не установлен. Установите: pip install opensearch-py")
    raise

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    logger.error("sentence-transformers не установлен. Установите: pip install sentence-transformers")
    raise

try:
    from langchain_community.vectorstores import OpenSearchVectorSearch
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError:
    OpenSearchVectorSearch = None
    HuggingFaceEmbeddings = None
    logger.warning("langchain_community не установлен. LangChain функции будут недоступны. Установите: pip install langchain-community")

try:
    from langchain.schema import Document
except ImportError:
    try:
        from langchain_core.documents import Document
    except ImportError:
        Document = None
        logger.debug("Document не найден, будет использоваться dict")


class OpenSearchManager:
    """Менеджер для работы с OpenSearch."""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        use_ssl: Optional[bool] = None,
        verify_certs: Optional[bool] = None,
        http_auth: Optional[Tuple[str, str]] = None,
        embedding_model: Optional[str] = None
    ):
        """
        Инициализация менеджера OpenSearch.
        
        Args:
            host: Хост OpenSearch (по умолчанию из OPENSEARCH_HOST или "localhost")
            port: Порт OpenSearch (по умолчанию из OPENSEARCH_PORT или 9200)
            use_ssl: Использовать SSL (None = автоопределение по порту или OPENSEARCH_USE_SSL)
            verify_certs: Проверять сертификаты (по умолчанию из OPENSEARCH_VERIFY_CERTS или True)
            http_auth: Кортеж (username, password) для аутентификации (из OPENSEARCH_USERNAME/PASSWORD)
            embedding_model: Модель для создания эмбеддингов (по умолчанию из EMBEDDING_MODEL)
        """
        # Загрузка параметров из переменных окружения, если не указаны явно
        if host is None:
            host = os.getenv("OPENSEARCH_HOST", "localhost")
        self.host = host
        
        if port is None:
            port = int(os.getenv("OPENSEARCH_PORT", "9200"))
        self.port = port
        
        if embedding_model is None:
            embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
        # Автоопределение SSL по порту или переменным окружения, если не указано явно
        if use_ssl is None:
            # Проверка переменной окружения
            env_ssl = os.getenv("OPENSEARCH_USE_SSL", "").lower()
            if env_ssl in ("true", "1", "yes"):
                use_ssl = True
            elif env_ssl in ("false", "0", "no"):
                use_ssl = False
            else:
                # Автоопределение по порту: 443 = HTTPS по умолчанию
                use_ssl = port == 443
        
        self.use_ssl = use_ssl
        
        # Загрузка verify_certs из переменных окружения, если не указано явно
        if verify_certs is None:
            verify_env = os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower()
            verify_certs = verify_env in ("true", "1", "yes")
        self.verify_certs = verify_certs
        
        # Загрузка аутентификации из переменных окружения, если не указано явно
        if http_auth is None:
            username = os.getenv("OPENSEARCH_USERNAME")
            password = os.getenv("OPENSEARCH_PASSWORD")
            if username and password:
                http_auth = (username, password)
        self.http_auth = http_auth
        
        # Логирование настроек подключения
        protocol = "HTTPS" if use_ssl else "HTTP"
        auth_info = f" (auth: {http_auth[0]})" if http_auth else ""
        logger.info(f"Подключение к OpenSearch: {protocol}://{host}:{port}{auth_info}")
        
        # Подключение к OpenSearch
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            connection_class=RequestsHttpConnection,
            timeout=30
        )
        
        # Загрузка модели эмбеддингов
        logger.info(f"Загрузка модели эмбеддингов: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        logger.info(f"Размерность эмбеддингов: {self.embedding_dim}")
        
        # LangChain embeddings для совместимости
        if HuggingFaceEmbeddings:
            try:
                self.langchain_embeddings = HuggingFaceEmbeddings(
                    model_name=embedding_model
                )
            except Exception as e:
                logger.warning(f"Не удалось создать HuggingFaceEmbeddings: {e}")
                self.langchain_embeddings = None
        else:
            self.langchain_embeddings = None
            logger.warning("HuggingFaceEmbeddings недоступен, LangChain функции будут ограничены")
    
    def check_connection(self) -> bool:
        """Проверка подключения к OpenSearch."""
        try:
            info = self.client.info()
            logger.info(f"Подключено к OpenSearch: {info['version']['number']}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к OpenSearch: {e}")
            return False
    
    def create_index(
        self,
        index_name: str,
        vector_dim: Optional[int] = None,
        settings: Optional[Dict] = None,
        force: bool = False
    ) -> bool:
        """
        Создание индекса с векторным полем.
        
        Args:
            index_name: Имя индекса
            vector_dim: Размерность вектора (по умолчанию из модели)
            settings: Дополнительные настройки индекса
            force: Если True, удаляет существующий индекс перед созданием
            
        Returns:
            True если успешно
        """
        if vector_dim is None:
            vector_dim = self.embedding_dim
        
        # Проверка существования индекса
        if self.client.indices.exists(index=index_name):
            if force:
                logger.warning(f"Индекс {index_name} уже существует. Удаление...")
                try:
                    self.client.indices.delete(index=index_name)
                    logger.info(f"Индекс {index_name} удален")
                except Exception as e:
                    logger.error(f"Ошибка удаления индекса {index_name}: {e}")
                    return False
            else:
                logger.warning(f"Индекс {index_name} уже существует. Используйте force=True для пересоздания")
                # Проверяем совместимость существующего индекса
                try:
                    existing_mapping = self.client.indices.get_mapping(index=index_name)
                    if index_name in existing_mapping:
                        props = existing_mapping[index_name].get('mappings', {}).get('properties', {})
                        if 'text_vector' in props:
                            existing_dim = props['text_vector'].get('dimension')
                            if existing_dim != vector_dim:
                                logger.error(
                                    f"Несовместимость размерности: существующий индекс имеет dimension={existing_dim}, "
                                    f"требуется {vector_dim}. Используйте force=True для пересоздания"
                                )
                                return False
                        logger.info(f"Индекс {index_name} существует и совместим")
                        return True
                except Exception as e:
                    logger.warning(f"Не удалось проверить существующий индекс: {e}")
                return False
        
        # Настройки по умолчанию
        default_settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 100
            }
        }
        
        if settings:
            default_settings.update(settings)
        
        # Маппинг индекса
        index_body = {
            "settings": default_settings,
            "mappings": {
                "properties": {
                    "text": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "text_vector": {
                        "type": "knn_vector",
                        "dimension": vector_dim,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",  # Правильное значение для OpenSearch
                            "engine": "lucene",  # Используем lucene вместо устаревшего nmslib
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24
                            }
                        }
                    },
                    "metadata": {
                        "type": "object",
                        "enabled": True
                    },
                    "layer": {"type": "keyword"},
                    "id": {"type": "integer"},
                    "lon": {"type": "float"},
                    "lat": {"type": "float"}
                }
            }
        }
        
        try:
            response = self.client.indices.create(index=index_name, body=index_body)
            logger.info(f"Индекс {index_name} создан успешно")
            return True
        except Exception as e:
            error_msg = str(e)
            # Детальная обработка ошибки 400
            if "400" in error_msg or "BadRequest" in error_msg or "mapper_parsing_exception" in error_msg:
                logger.error(f"Ошибка 400 при создании индекса {index_name}: {error_msg}")
                logger.info("Возможные причины:")
                logger.info("  1. Индекс уже существует с другой конфигурацией")
                logger.info("  2. Несовместимость размерности вектора")
                logger.info("  3. Устаревший движок (nmslib) - используйте lucene или faiss")
                logger.info("  4. Неправильный формат настроек")
                logger.info(f"Решение: Используйте create_index('{index_name}', force=True) для пересоздания")
            else:
                logger.error(f"Ошибка создания индекса {index_name}: {e}")
            return False
    
    def delete_index(self, index_name: str, ignore_missing: bool = True) -> bool:
        """
        Удаление индекса.
        
        Args:
            index_name: Имя индекса
            ignore_missing: Если True, не выдает ошибку если индекс не существует
            
        Returns:
            True если успешно
        """
        try:
            if not self.client.indices.exists(index=index_name):
                if ignore_missing:
                    logger.info(f"Индекс {index_name} не существует, пропускаем удаление")
                    return True
                else:
                    logger.warning(f"Индекс {index_name} не существует")
                    return False
            
            self.client.indices.delete(index=index_name)
            logger.info(f"Индекс {index_name} удален")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления индекса {index_name}: {e}")
            return False
    
    def recreate_index(
        self,
        index_name: str,
        vector_dim: Optional[int] = None,
        settings: Optional[Dict] = None
    ) -> bool:
        """
        Пересоздание индекса (удаление + создание).
        
        Args:
            index_name: Имя индекса
            vector_dim: Размерность вектора
            settings: Дополнительные настройки индекса
            
        Returns:
            True если успешно
        """
        logger.info(f"Пересоздание индекса {index_name}...")
        if self.delete_index(index_name, ignore_missing=True):
            return self.create_index(index_name, vector_dim=vector_dim, settings=settings)
        return False
    
    def create_text_from_row(self, row: Dict) -> str:
        """
        Создание текстового представления строки данных для индексации.
        
        Args:
            row: Словарь с данными строки
            
        Returns:
            Текстовое представление
        """
        parts = []
        
        # Основная информация
        if 'layer' in row:
            parts.append(f"Слой: {row['layer']}")
        
        # Географические координаты
        if 'lon' in row and 'lat' in row and pd.notna(row['lon']) and pd.notna(row['lat']):
            parts.append(f"Координаты: {row['lon']:.6f}, {row['lat']:.6f}")
        
        # Атрибуты
        for key, value in row.items():
            if key in ['layer', 'id', 'lon', 'lat', 'text', 'text_vector', 'metadata']:
                continue
            
            if pd.notna(value) and value not in ['', 'unknown', None]:
                # Очистка имени поля
                clean_key = str(key).replace('_', ' ').title()
                parts.append(f"{clean_key}: {value}")
        
        return ". ".join(parts)
    
    def index_dataframe(
        self,
        df: pd.DataFrame,
        index_name: str,
        text_columns: Optional[List[str]] = None,
        batch_size: int = 100,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Индексация DataFrame в OpenSearch.
        
        Args:
            df: DataFrame для индексации
            index_name: Имя индекса
            text_columns: Колонки для создания текста (None = все)
            batch_size: Размер батча
            progress_callback: Функция для отслеживания прогресса
            
        Returns:
            True если успешно
        """
        if not self.client.indices.exists(index=index_name):
            logger.error(f"Индекс {index_name} не существует. Создайте его сначала.")
            return False
        
        total_rows = len(df)
        logger.info(f"Начало индексации {total_rows} строк в индекс {index_name}")
        
        actions = []
        processed = 0
        
        for idx, row in df.iterrows():
            try:
                # Создание текста
                text = self.create_text_from_row(row.to_dict())
                
                # Создание эмбеддинга
                embedding = self.embedding_model.encode(text).tolist()
                
                # Подготовка документа
                doc = {
                    "_index": index_name,
                    "_id": int(row.get('id', idx)),
                    "text": text,
                    "text_vector": embedding,
                    "layer": str(row.get('layer', 'unknown')),
                    "id": int(row.get('id', idx)),
                    "lon": float(row.get('lon', 0.0)) if pd.notna(row.get('lon')) else None,
                    "lat": float(row.get('lat', 0.0)) if pd.notna(row.get('lat')) else None,
                    "metadata": {
                        k: str(v) if pd.notna(v) else None
                        for k, v in row.items()
                        if k not in ['text', 'text_vector', 'layer', 'id', 'lon', 'lat']
                    }
                }
                
                actions.append(doc)
                processed += 1
                
                # Батчинг
                if len(actions) >= batch_size:
                    success, failed = bulk(self.client, actions, chunk_size=batch_size)
                    logger.debug(f"Индексировано: {success}, ошибок: {failed}")
                    actions = []
                
                # Прогресс
                if progress_callback and processed % 100 == 0:
                    progress_callback(processed, total_rows)
                    
            except Exception as e:
                logger.error(f"Ошибка обработки строки {idx}: {e}")
                continue
        
        # Обработка оставшихся документов
        if actions:
            success, failed = bulk(self.client, actions, chunk_size=batch_size)
            logger.debug(f"Индексировано: {success}, ошибок: {failed}")
        
        logger.info(f"Индексация завершена: {processed}/{total_rows} строк")
        return True
    
    def search(
        self,
        query: str,
        index_name: str,
        top_k: int = 10,
        filter_dict: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Семантический поиск в OpenSearch.
        
        Args:
            query: Текстовый запрос
            index_name: Имя индекса
            top_k: Количество результатов
            filter_dict: Фильтры для поиска
            
        Returns:
            Список результатов поиска
        """
        if not self.client.indices.exists(index=index_name):
            logger.error(f"Индекс {index_name} не существует")
            return []
        
        # Создание эмбеддинга запроса
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Построение запроса
        search_body = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "text_vector": {
                                    "vector": query_embedding,
                                    "k": top_k
                                }
                            }
                        }
                    ]
                }
            },
            "_source": ["text", "layer", "id", "lon", "lat", "metadata"]
        }
        
        # Добавление фильтров
        if filter_dict:
            filters = []
            for key, value in filter_dict.items():
                filters.append({"term": {key: value}})
            if filters:
                search_body["query"]["bool"]["filter"] = filters
        
        try:
            response = self.client.search(index=index_name, body=search_body)
            results = []
            
            for hit in response['hits']['hits']:
                results.append({
                    'score': hit['_score'],
                    'text': hit['_source'].get('text', ''),
                    'layer': hit['_source'].get('layer', ''),
                    'id': hit['_source'].get('id', ''),
                    'lon': hit['_source'].get('lon'),
                    'lat': hit['_source'].get('lat'),
                    'metadata': hit['_source'].get('metadata', {})
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return []
    
    def get_langchain_vectorstore(
        self,
        index_name: str
    ) -> Optional[Any]:
        """
        Создание LangChain VectorStore для интеграции с RAG.
        
        Args:
            index_name: Имя индекса
            
        Returns:
            OpenSearchVectorSearch объект или None если недоступен
        """
        if OpenSearchVectorSearch is None:
            logger.warning("OpenSearchVectorSearch недоступен. Установите langchain-community")
            return None
        
        if HuggingFaceEmbeddings is None:
            logger.warning("HuggingFaceEmbeddings недоступен. Установите langchain-community")
            return None
        
        try:
            return OpenSearchVectorSearch(
                opensearch_url=f"{'https' if self.use_ssl else 'http'}://{self.host}:{self.port}",
                index_name=index_name,
                embedding_function=self.langchain_embeddings,
                http_auth=self.http_auth,
                use_ssl=self.use_ssl,
                verify_certs=self.verify_certs
            )
        except Exception as e:
            logger.error(f"Ошибка создания VectorStore: {e}")
            return None
    
    def get_index_stats(self, index_name: str) -> Dict:
        """Получение статистики индекса."""
        try:
            if not self.client.indices.exists(index=index_name):
                return {}
            
            stats = self.client.indices.stats(index=index_name)
            return {
                'doc_count': stats['indices'][index_name]['total']['docs']['count'],
                'size': stats['indices'][index_name]['total']['store']['size_in_bytes'],
                'index_size': stats['indices'][index_name]['total']['indexing']['index_size_in_bytes']
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}


# Пример использования
if __name__ == "__main__":
    # Инициализация для HTTPS
    manager = OpenSearchManager(
        host="localhost",
        port=9200,  # Или 443 для стандартного HTTPS
        use_ssl=True,  # Включить HTTPS
        verify_certs=False,  # Проверять сертификаты
        http_auth=("admin", "Rodion1killer"),  # Если требуется аутентификация
        embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    # Проверка подключения
    if not manager.check_connection():
        print("Не удалось подключиться к OpenSearch")
        exit(1)
    
    # Создание индекса
    index_name = "caspian_data"
    manager.create_index(index_name)
    
    # Загрузка данных
    df = pd.read_csv("ЦК(25.06.25)/pars_test.csv")
    
    # Индексация (первые 1000 строк для примера)
    df_sample = df.head(1000)
    manager.index_dataframe(
        df_sample,
        index_name,
        progress_callback=lambda c, t: print(f"Прогресс: {c}/{t}")
    )
    
    # Поиск
    results = manager.search("месторождения нефти", index_name, top_k=5)
    print("\nРезультаты поиска:")
    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result['score']:.4f}")
        print(f"   Text: {result['text'][:200]}...")
        print()
    
    # Статистика
    stats = manager.get_index_stats(index_name)
    print(f"Статистика индекса: {stats}")

