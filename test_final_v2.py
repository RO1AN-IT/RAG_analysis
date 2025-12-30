"""
RAG система через LangChain для поиска геологических признаков.

Алгоритм:
1. Получаем запрос пользователя
2. Генерируем описание признака через GigaChat
3. Векторизуем и ищем в OpenSearch (rag_descriptions)
4. Берем топ-k результатов
5. Проверяем каждый признак через GigaChat
6. Составляем SQL запрос для найденных признаков
7. Подводим итоги через GigaChat (роль: преподаватель)
"""

import logging
import pandas as pd
from typing import List, Dict, Optional, Tuple, Any
from langchain_core.documents import Document
from opensearchpy import OpenSearch
from gigachat import GigaChat
from sentence_transformers import SentenceTransformer
import duckdb
from prompts import (
    FEATURE_DESCRIPTION_PROMPT,
    FEATURE_MATCH_PROMPT,
    SQL_GENERATION_PROMPT,
    SQL_FIX_PROMPT,
    SQL_FIX_PROMPT_V2,
    FINAL_SUMMARY_PROMPT
)
GIGACHAT_CREDENTIALS = "MDE5OWUyNTAtNGNhZS03ZDdjLTg2ZmMtZjM5NDE0ZGFhNjUzOmYzMTk3ZWUyLTBlNTYtNDUzNy04ZWViLTUyZWU4ZjAyZGMzZA=="

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RAGSystemLangChain:
    """
    RAG система через LangChain для поиска геологических признаков.
    """
    
    def __init__(
        self,
        opensearch_host: str = "localhost",
        opensearch_port: int = 9200,
        opensearch_use_ssl: bool = True,
        opensearch_verify_certs: bool = False,
        opensearch_auth: Optional[tuple] = None,
        opensearch_index_descriptions: str = "rag_descriptions",
        opensearch_index_layers: str = "rag_layers",
        embedding_model_name: str = "ai-forever/sbert_large_nlu_ru",
        credentials: str = GIGACHAT_CREDENTIALS
    ):
        """
        Инициализация RAG системы.
        
        Args:
            opensearch_host: Хост OpenSearch
            opensearch_port: Порт OpenSearch
            opensearch_use_ssl: Использовать SSL
            opensearch_verify_certs: Проверять сертификаты
            opensearch_auth: Учетные данные (username, password)
            opensearch_index_descriptions: Имя индекса с описаниями признаков (rag_descriptions)
            opensearch_index_layers: Имя индекса с геологическими данными (rag_layers)
            embedding_model_name: Название модели для эмбеддингов
            credentials: Учетные данные GigaChat
        """
        self.credentials = credentials
        self.opensearch_index_descriptions = opensearch_index_descriptions
        self.opensearch_index_layers = opensearch_index_layers
        
        # Создание клиента OpenSearch
        logger.info(f"Подключение к OpenSearch: {opensearch_host}:{opensearch_port} (SSL: {opensearch_use_ssl}, verify_certs: {opensearch_verify_certs})")
        
        # Всегда используем указанные настройки SSL (SSL=True, verify_certs=False)
        self.opensearch_client = OpenSearch(
            hosts=[{'host': opensearch_host, 'port': opensearch_port}],
            http_auth=opensearch_auth,
            use_ssl=opensearch_use_ssl,
            verify_certs=opensearch_verify_certs,
            timeout=60,  # Увеличиваем таймаут
            max_retries=5,  # Больше попыток
            retry_on_timeout=True,
            ssl_show_warn=False  # Отключаем предупреждения SSL
        )
        
        # Проверка подключения с повторными попытками
        max_ping_attempts = 3
        ping_success = False
        for attempt in range(max_ping_attempts):
            try:
                if self.opensearch_client.ping():
                    ping_success = True
                    logger.info("Подключение к OpenSearch установлено")
                    break
                else:
                    logger.warning(f"Попытка {attempt + 1}/{max_ping_attempts}: OpenSearch не отвечает на ping")
            except Exception as ping_error:
                logger.warning(f"Попытка {attempt + 1}/{max_ping_attempts}: Ошибка ping - {type(ping_error).__name__}: {str(ping_error)[:100]}")
                if attempt < max_ping_attempts - 1:
                    import time
                    time.sleep(2)  # Ждем перед следующей попыткой
        
        if not ping_success:
            logger.error("Не удалось установить подключение к OpenSearch после всех попыток")
            logger.error("Проверьте, что OpenSearch запущен и доступен на указанном адресе")
            logger.error("Система продолжит работу, но функциональность будет ограничена")
        
        # Определение имени поля для векторов в индексе описаний (только если подключение успешно)
        if ping_success:
            try:
                self.vector_field_name = self._get_vector_field_name(opensearch_index_descriptions)
                self.text_field_name = self._get_text_field_name(opensearch_index_descriptions)
            except Exception as e:
                logger.warning(f"Ошибка определения полей: {e}. Используем значения по умолчанию")
                self.vector_field_name = "embedding"
                self.text_field_name = "text"
        else:
            # Используем значения по умолчанию, если подключение не установлено
            self.vector_field_name = "embedding"
            self.text_field_name = "text"
            logger.warning("Используются значения по умолчанию для полей векторов и текста")
        
        # Инициализация модели эмбеддингов (используем SentenceTransformer напрямую)
        logger.info(f"Загрузка модели эмбеддингов: {embedding_model_name}")
        self.embedding_model = SentenceTransformer(embedding_model_name)
        
        # Загрузка всех документов из индекса rag_layers для SQL запросов (только если подключение успешно)
        if ping_success:
            try:
                logger.info(f"Загрузка всех документов из индекса {opensearch_index_layers}...")
                self.df = self._load_all_documents_from_opensearch()
                logger.info(f"Загружено {len(self.df)} документов, {len(self.df.columns)} колонок")
            except Exception as e:
                logger.error(f"Ошибка загрузки документов из OpenSearch: {e}")
                self.df = pd.DataFrame()  # Пустой DataFrame
        else:
            logger.warning("Пропускаем загрузку документов из OpenSearch - подключение не установлено")
            self.df = pd.DataFrame()  # Пустой DataFrame
        
        logger.info("RAG система инициализирована")
    
    def _get_vector_field_name(self, index_name: str) -> str:
        """
        Определение имени поля для векторов в индексе.
        
        Args:
            index_name: Имя индекса
            
        Returns:
            Имя поля для векторов
        """
        try:
            # Получаем mapping индекса
            mapping = self.opensearch_client.indices.get_mapping(index=index_name)
            index_mapping = mapping.get(index_name, {}).get('mappings', {}).get('properties', {})
            
            # Ищем поле типа knn_vector
            for field_name, field_props in index_mapping.items():
                if field_props.get('type') == 'knn_vector':
                    logger.info(f"Найдено поле для векторов: {field_name}")
                    return field_name
            
            # Если не найдено, пробуем стандартные имена
            for default_name in ['embedding', 'vector', 'vector_field', 'embedding_field']:
                if default_name in index_mapping:
                    logger.warning(f"Поле {default_name} найдено, но не имеет тип knn_vector. Используем его.")
                    return default_name
            
            logger.warning("Поле для векторов не найдено, используем 'embedding' по умолчанию")
            return "embedding"
        except Exception as e:
            logger.warning(f"Ошибка при определении поля для векторов: {e}. Используем 'embedding' по умолчанию")
            return "embedding"
    
    def _get_text_field_name(self, index_name: str) -> str:
        """
        Определение имени поля для текста в индексе.
        
        Args:
            index_name: Имя индекса
            
        Returns:
            Имя поля для текста
        """
        try:
            # Получаем mapping индекса
            mapping = self.opensearch_client.indices.get_mapping(index=index_name)
            index_mapping = mapping.get(index_name, {}).get('mappings', {}).get('properties', {})
            
            # Ищем поле типа text
            for field_name, field_props in index_mapping.items():
                if field_props.get('type') == 'text':
                    logger.info(f"Найдено текстовое поле: {field_name}")
                    return field_name
            
            # Если не найдено, используем стандартное имя
            logger.warning("Текстовое поле не найдено, используем 'text' по умолчанию")
            return "text"
        except Exception as e:
            logger.warning(f"Ошибка при определении текстового поля: {e}. Используем 'text' по умолчанию")
            return "text"
    
    def _load_all_documents_from_opensearch(self) -> pd.DataFrame:
        """
        Загрузка всех документов из индекса rag_layers в DataFrame.
        Использует scroll API для получения всех документов.
        
        Returns:
            DataFrame со всеми документами из индекса
        """
        logger.info(f"Начало загрузки всех документов из индекса {self.opensearch_index_layers}...")
        
        all_documents = []
        scroll_size = 1000  # Размер батча для scroll
        
        try:
            # Начальный запрос с scroll
            response = self.opensearch_client.search(
                index=self.opensearch_index_layers,
                body={
                    "query": {"match_all": {}},
                    "size": scroll_size 
                },
                scroll='5m'  # Время жизни scroll контекста
            )
            
            scroll_id = response.get('_scroll_id')
            hits = response['hits']['hits']
            total_hits = response['hits']['total']
            
            # Обработка total (может быть int или dict с value)
            if isinstance(total_hits, dict):
                total_count = total_hits.get('value', 0)
            else:
                total_count = total_hits
            
            logger.info(f"Всего документов в индексе: {total_count}")
            
            # Обработка первой партии
            for hit in hits:
                source = hit['_source']
                # Добавляем _id в документ
                source['_id'] = hit['_id']
                all_documents.append(source)
            
            processed = len(hits)
            logger.info(f"Загружено {processed}/{total_count} документов...")
            
            # Продолжаем scroll пока есть результаты
            while len(hits) > 0:
                response = self.opensearch_client.scroll(
                    scroll_id=scroll_id,
                    scroll='5m'
                )
                
                scroll_id = response.get('_scroll_id')
                hits = response['hits']['hits']
                
                for hit in hits:
                    source = hit['_source']
                    source['_id'] = hit['_id']
                    all_documents.append(source)
                
                processed += len(hits)
                if processed % 5000 == 0:
                    logger.info(f"Загружено {processed}/{total_count} документов...")
            
            # Очистка scroll контекста
            if scroll_id:
                try:
                    self.opensearch_client.clear_scroll(scroll_id=scroll_id)
                except:
                    pass
            
            logger.info(f"Загрузка завершена: {len(all_documents)} документов")
            
            # Преобразование в DataFrame
            if all_documents:
                df = pd.DataFrame(all_documents)
                logger.info(f"DataFrame создан: {len(df)} строк, {len(df.columns)} колонок")
                return df
            else:
                logger.warning("Не найдено документов в индексе")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Ошибка загрузки документов из OpenSearch: {e}")
            raise
    
    def generate_feature_description(self, user_query: str) -> str:
        """
        Генерация описания признака или общего описания запроса через GigaChat.
        
        Args:
            user_query: Запрос пользователя
            
        Returns:
            Описание признака или запроса
        """
        logger.info(f"Генерация описания для запроса: {user_query}")
        
        prompt = FEATURE_DESCRIPTION_PROMPT.format(user_query=user_query)
        
        try:
            with GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False,
                scope='GIGACHAT_API_B2B',
                model='GigaChat-2-Pro'
            ) as giga:
                response = giga.chat(prompt)
                description = response.choices[0].message.content.strip()
                logger.info(f"Сгенерировано описание: {description[:100]}...")
                return description
        except Exception as e:
            logger.error(f"Ошибка генерации описания: {e}")
            # Возвращаем исходный запрос как описание
            return user_query
    
    def search_in_opensearch(self, query: str, top_k: int = 10) -> List[Document]:
        """
        Поиск в OpenSearch по косинусному расстоянию (прямой KNN поиск без LangChain).
        
        Args:
            query: Текстовый запрос
            top_k: Количество результатов
            
        Returns:
            Список найденных документов
        """
        logger.info(f"Поиск в OpenSearch: '{query[:50]}...' (топ-{top_k})")
        
        try:
            # Генерируем эмбеддинг для запроса
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Формируем KNN запрос для OpenSearch
            # Правильный формат: KNN внутри query
            knn_query = {
                "size": top_k,
                "query": {
                    "knn": {
                        self.vector_field_name: {
                            "vector": query_embedding,
                            "k": top_k
                        }
                    }
                }
            }
            
            # Выполняем поиск
            response = self.opensearch_client.search(
                index=self.opensearch_index_descriptions,
                body=knn_query
            )
            
            # Преобразуем результаты в Document объекты
            documents = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                text = source.get(self.text_field_name, '')
                
                # Извлекаем метаданные (все поля кроме текста и эмбеддинга)
                metadata = {k: v for k, v in source.items() 
                           if k != self.text_field_name and k != self.vector_field_name}
                metadata['_id'] = hit['_id']
                metadata['_score'] = hit['_score']
                
                doc = Document(page_content=text, metadata=metadata)
                documents.append(doc)
            
            logger.info(f"Найдено {len(documents)} документов")
            return documents
        except Exception as e:
            logger.error(f"Ошибка поиска в OpenSearch: {e}")
            return []
    
    def check_feature_match(self, user_query: str, feature_name: str, feature_description: str) -> bool:
        """
        Проверка, соответствует ли признак запросу пользователя.
        
        Args:
            user_query: Исходный запрос пользователя
            feature_name: Название признака
            feature_description: Описание признака
            
        Returns:
            True если признак соответствует, False иначе
        """
        logger.info(f"Проверка соответствия признака '{feature_name}' запросу пользователя")
        
        prompt = FEATURE_MATCH_PROMPT.format(
            user_query=user_query,
            feature_name=feature_name,
            feature_description=feature_description
        )
        
        try:
            with GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False,
                scope='GIGACHAT_API_B2B',
                model='GigaChat-2-Pro'
            ) as giga:
                response = giga.chat(prompt)
                answer = response.choices[0].message.content.strip().upper()
                
                # Проверяем ответ
                if "ДА" in answer or "YES" in answer:
                    logger.info(f"Признак '{feature_name}' соответствует запросу")
                    return True
                else:
                    logger.info(f"Признак '{feature_name}' не соответствует запросу")
                    return False
        except Exception as e:
            logger.error(f"Ошибка проверки соответствия признака: {e}")
            # В случае ошибки считаем, что признак не соответствует
            return False
    
    def get_columns_info(self) -> str:
        """Получение информации о колонках для промпта."""
        columns_info = []
        for col in self.df.columns:
            dtype = str(self.df[col].dtype)
            non_null_count = self.df[col].notna().sum()
            columns_info.append(f"- `{col}` ({dtype}, заполнено: {non_null_count}/{len(self.df)})")
        return "\n".join(columns_info)
    
    def generate_sql_query(
        self,
        user_query: str,
        feature_name: str,
        feature_description: str,
        max_attempts: int = 3
    ) -> Optional[str]:
        """
        Генерация SQL запроса на основе найденного признака с трехфакторной проверкой.
        Если запрос выполняется с ошибкой, запрашивается исправление.
        
        Args:
            user_query: Исходный запрос пользователя
            feature_name: Название признака
            feature_description: Описание признака
            max_attempts: Максимальное количество попыток генерации (по умолчанию 3)
            
        Returns:
            SQL запрос или None в случае ошибки
        """
        logger.info(f"Генерация SQL запроса для признака '{feature_name}' (максимум {max_attempts} попыток)")
        
        columns_info = self.get_columns_info()
        sql_query = None
        attempt = 0
        error_history = []  # История всех ошибок для третьей попытки
        all_candidate_bindings = []  # Все candidate bindings из всех ошибок
        
        while attempt < max_attempts:
            attempt += 1
            logger.info(f"Попытка {attempt}/{max_attempts} генерации SQL запроса")
            
            try:
                if attempt == 1:
                    # Первая попытка - обычная генерация
                    prompt = SQL_GENERATION_PROMPT.format(
                        user_query=user_query,
                        feature_name=feature_name,
                        feature_description=feature_description,
                        columns_info=columns_info
                    )
                elif attempt == 2:
                    # Вторая попытка - исправление ошибки
                    error_msg = str(self.last_sql_error) if hasattr(self, 'last_sql_error') else "Неизвестная ошибка"
                    candidate_bindings = getattr(self, 'last_candidate_bindings', [])
                    # Используем уникальные candidate bindings
                    unique_bindings = list(set(candidate_bindings))
                    candidate_bindings_text = "\n".join([f"- `{col}`" for col in unique_bindings]) if unique_bindings else "Не указаны"
                    prompt = SQL_FIX_PROMPT.format(
                        user_query=user_query,
                        feature_name=feature_name,
                        feature_description=feature_description,
                        columns_info=columns_info,
                        sql_query=sql_query or "",
                        error_message=error_msg,
                        candidate_bindings=candidate_bindings_text
                    )
                else:
                    # Третья попытка - глубокое исправление с учетом всей истории ошибок
                    error_msg = str(self.last_sql_error) if hasattr(self, 'last_sql_error') else "Неизвестная ошибка"
                    error_history_text = "\n".join(error_history) if error_history else "История ошибок отсутствует"
                    # Используем все candidate bindings из всех ошибок
                    if all_candidate_bindings:
                        unique_bindings = list(set(all_candidate_bindings))
                    else:
                        unique_bindings = list(set(getattr(self, 'last_candidate_bindings', [])))
                    candidate_bindings_text = "\n".join([f"- `{col}`" for col in unique_bindings]) if unique_bindings else "Не указаны"
                    prompt = SQL_FIX_PROMPT_V2.format(
                        user_query=user_query,
                        feature_name=feature_name,
                        feature_description=feature_description,
                        columns_info=columns_info,
                        sql_query=sql_query or "",
                        error_message=error_msg,
                        error_history=error_history_text,
                        candidate_bindings=candidate_bindings_text
                    )
                
                with GigaChat(
                    credentials=self.credentials,
                    verify_ssl_certs=False,
                    scope='GIGACHAT_API_B2B',
                    model='GigaChat-2-Pro'
                ) as giga:
                    response = giga.chat(prompt)
                    sql_query = response.choices[0].message.content.strip()
                    
                    # Очистка SQL запроса от markdown форматирования, если есть
                    if sql_query.startswith("```sql"):
                        sql_query = sql_query[6:]
                    if sql_query.startswith("```"):
                        sql_query = sql_query[3:]
                    if sql_query.endswith("```"):
                        sql_query = sql_query[:-3]
                    sql_query = sql_query.strip()
                    
                    logger.info(f"Сгенерирован SQL запрос (попытка {attempt}): {sql_query[:100]}...")
                    
                    # Пробуем выполнить запрос для проверки
                    try:
                        test_result = self.execute_sql_query(sql_query, test_mode=True)
                        
                        if test_result is not None:
                            # Запрос выполнился успешно
                            logger.info(f"SQL запрос успешно проверен на попытке {attempt}")
                            return sql_query
                        else:
                            # Запрос выполнился с ошибкой, продолжаем попытки
                            if attempt < max_attempts:
                                error_msg = str(self.last_sql_error) if hasattr(self, 'last_sql_error') else "Неизвестная ошибка"
                                error_history.append(f"Попытка {attempt}: {error_msg}")
                                # Сохраняем candidate bindings из текущей ошибки, если они есть
                                if hasattr(self, 'last_candidate_bindings') and self.last_candidate_bindings:
                                    all_candidate_bindings.extend(self.last_candidate_bindings)
                                    error_history.append(f"Доступные колонки: {', '.join(self.last_candidate_bindings)}")
                                logger.warning(f"SQL запрос выполнился с ошибкой: {error_msg[:200]}... Пробуем исправить (попытка {attempt}/{max_attempts})")
                                continue
                            else:
                                logger.error(f"Не удалось сгенерировать корректный SQL запрос после {max_attempts} попыток")
                                return None
                    except Exception as test_error:
                        # Ошибка при тестировании запроса
                        self.last_sql_error = test_error
                        if attempt < max_attempts:
                            error_msg = str(test_error)
                            error_history.append(f"Попытка {attempt}: {error_msg}")
                            # Извлекаем candidate bindings из ошибки
                            candidate_bindings = self._extract_candidate_bindings(error_msg)
                            if candidate_bindings:
                                self.last_candidate_bindings = candidate_bindings
                                all_candidate_bindings.extend(candidate_bindings)
                                error_history.append(f"Доступные колонки: {', '.join(candidate_bindings)}")
                                logger.info(f"Найдены доступные колонки в ошибке: {candidate_bindings}")
                            logger.warning(f"Ошибка при тестировании SQL запроса: {test_error}. Пробуем исправить (попытка {attempt}/{max_attempts})")
                            continue
                        else:
                            logger.error(f"Не удалось сгенерировать корректный SQL запрос после {max_attempts} попыток")
                            return None
                            
            except Exception as e:
                logger.error(f"Ошибка генерации SQL запроса на попытке {attempt}: {e}")
                if attempt >= max_attempts:
                    return None
                continue
        
        return sql_query
    
    def _extract_candidate_bindings(self, error_msg: str) -> List[str]:
        """
        Извлекает candidate bindings из сообщения об ошибке DuckDB.
        
        Args:
            error_msg: Сообщение об ошибке
            
        Returns:
            Список доступных имен колонок из ошибки
        """
        import re
        candidate_bindings = []
        
        # Ищем паттерн "Candidate bindings: ..."
        match = re.search(r'Candidate bindings:\s*([^\n]+)', error_msg)
        if match:
            bindings_str = match.group(1)
            # Извлекаем имена в кавычках
            bindings = re.findall(r'"([^"]+)"', bindings_str)
            candidate_bindings.extend(bindings)
        
        return candidate_bindings
    
    def execute_sql_query(self, sql_query: str, test_mode: bool = False) -> Optional[pd.DataFrame]:
        """
        Выполнение SQL запроса через DuckDB.
        
        Args:
            sql_query: SQL запрос
            test_mode: Если True, сохраняет ошибку для последующего исправления
            
        Returns:
            DataFrame с результатами или None в случае ошибки (в test_mode)
        """
        logger.info(f"Выполнение SQL запроса: {sql_query[:100]}...")
        
        try:
            # Создаем соединение с DuckDB
            conn = duckdb.connect()
            
            # Регистрируем DataFrame как таблицу
            conn.register('df', self.df)
            
            # Выполняем запрос
            result = conn.execute(sql_query).fetchdf()
            
            conn.close()
            
            logger.info(f"SQL запрос выполнен, найдено {len(result)} строк")
            return result
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка выполнения SQL запроса: {error_msg}")
            
            # Сохраняем ошибку для последующего исправления
            if test_mode:
                self.last_sql_error = e
                # Извлекаем candidate bindings из ошибки
                candidate_bindings = self._extract_candidate_bindings(error_msg)
                if candidate_bindings:
                    self.last_candidate_bindings = candidate_bindings
                    logger.info(f"Найдены доступные колонки в ошибке: {candidate_bindings}")
                return None
            else:
                return pd.DataFrame()
    
    def generate_final_summary(
        self,
        user_query: str,
        results_df: pd.DataFrame
    ) -> str:
        """
        Генерация финального ответа через GigaChat (роль: преподаватель).
        
        Args:
            user_query: Исходный запрос пользователя
            results_df: DataFrame с результатами поиска
            
        Returns:
            Финальный ответ преподавателя
        """
        logger.info("Генерация финального ответа преподавателя")
        
        # Подготовка данных для промпта
        if results_df.empty:
            retrieved_data = "Данные не найдены в базе."
            coordinates_section = ""
        else:
            # Ограничиваем размер данных для промпта (первые 10 записей)
            # Но координаты извлекаем из всех результатов для отображения на карте
            max_rows_for_prompt = 10
            total_results = len(results_df)
            if total_results > max_rows_for_prompt:
                retrieved_data = f"Найдено {total_results} записей. Показаны первые {max_rows_for_prompt}:\n\n"
                retrieved_data += results_df.head(max_rows_for_prompt).to_string(index=False)
            else:
                retrieved_data = results_df.to_string(index=False)
            
            # Извлечение координат из ВСЕХ результатов (для отображения на карте)
            coordinates_list = []
            if 'lon' in results_df.columns and 'lat' in results_df.columns:
                for idx, row in results_df.iterrows():
                    lon = row.get('lon', None)
                    lat = row.get('lat', None)
                    
                    if pd.notna(lon) and pd.notna(lat):
                        lon_str = str(lon).strip()
                        lat_str = str(lat).strip()
                        
                        # Обработка массивов координат
                        if lon_str.startswith('['):
                            try:
                                import ast
                                lon_array = ast.literal_eval(lon_str)
                                if isinstance(lon_array, list) and len(lon_array) > 0:
                                    lon_str = str(lon_array[0])
                            except:
                                lon_str = lon_str.strip('[]').split(',')[0].strip()
                        
                        if lat_str.startswith('['):
                            try:
                                import ast
                                lat_array = ast.literal_eval(lat_str)
                                if isinstance(lat_array, list) and len(lat_array) > 0:
                                    lat_str = str(lat_array[-1]) if len(lat_array) > 1 else str(lat_array[0])
                            except:
                                lat_str = lat_str.strip('[]').split(',')[-1].strip()
                        
                        if lon_str and lat_str and lon_str not in ['nan', 'None'] and lat_str not in ['nan', 'None']:
                            coordinates_list.append(f"Запись {idx + 1}: Долгота: {lon_str}, Широта: {lat_str}")
            
            # Формируем секцию с координатами (все координаты, не только первые 10)
            # Но в тексте указываем, что для промпта показаны только первые 10 записей
            if coordinates_list:
                coords_text = "\n".join(coordinates_list)
                if total_results > max_rows_for_prompt:
                    coords_text = f"Всего найдено {total_results} записей с координатами. В данных для анализа показаны первые {max_rows_for_prompt} записей, но все координаты доступны на карте.\n\n" + coords_text
                coordinates_section = "\n\n" + "="*60 + "\nКООРДИНАТЫ НАЙДЕННЫХ ЗАПИСЕЙ:\n" + "="*60 + "\n" + coords_text + "\n" + "="*60
            else:
                coordinates_section = "\n\n⚠️ ВНИМАНИЕ: Координаты не найдены в данных."
        
        prompt = FINAL_SUMMARY_PROMPT.format(
            user_query=user_query,
            retrieved_data=retrieved_data,
            coordinates_section=coordinates_section
        )
        
        try:
            with GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False,
                scope='GIGACHAT_API_B2B',
                model='GigaChat-2-Pro'
            ) as giga:
                response = giga.chat(prompt)
                summary = response.choices[0].message.content.strip()
                
                # Проверяем, что координаты включены в ответ
                if coordinates_section and 'координат' not in summary.lower() and '📍' not in summary:
                    logger.warning("Координаты не включены в ответ, добавляем принудительно")
                    coords_text = "\n\n📍 КООРДИНАТЫ НАЙДЕННЫХ ЗАПИСЕЙ:\n" + "\n".join([line.replace("Запись ", "• ") for line in coordinates_list])
                    summary += coords_text
                
                logger.info("Финальный ответ сгенерирован")
                return summary
        except Exception as e:
            logger.error(f"Ошибка генерации финального ответа: {e}")
            # Возвращаем базовый ответ с координатами
            if results_df.empty:
                return "К сожалению, по вашему запросу данные в базе не найдены."
            else:
                fallback = f"Найдено {len(results_df)} записей:\n\n{retrieved_data}"
                if coordinates_section:
                    fallback += coordinates_section
                return fallback
    
    def query(
        self,
        user_query: str,
        top_k: int = 10
    ) -> Tuple[pd.DataFrame, str]:
        """
        Выполнение полного цикла RAG запроса.
        
        Args:
            user_query: Запрос пользователя
            top_k: Количество топ результатов из OpenSearch
            
        Returns:
            Tuple[DataFrame с результатами, Финальный ответ]
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"RAG ЗАПРОС: {user_query}")
        logger.info(f"{'='*80}\n")
        
        # Шаг 1: Генерация описания признака или запроса
        logger.info("ШАГ 1: Генерация описания признака/запроса")
        feature_description = self.generate_feature_description(user_query)
        
        # Шаг 2: Поиск в OpenSearch
        logger.info(f"ШАГ 2: Поиск в OpenSearch (топ-{top_k})")
        search_results = self.search_in_opensearch(feature_description, top_k=top_k)
        
        if not search_results:
            logger.warning("Не найдено результатов в OpenSearch")
            return pd.DataFrame(), "К сожалению, по вашему запросу не найдено релевантных признаков в базе."
        
        # Шаг 3: Проверка каждого признака
        logger.info(f"ШАГ 3: Проверка {len(search_results)} признаков")
        matched_features = []
        
        for doc in search_results:
            # Извлекаем feature_name из метаданных
            # В индексе rag_descriptions поле feature_name хранится в метаданных
            feature_name = doc.metadata.get('feature_name', '')
            
            # Если нет в метаданных, пытаемся извлечь из других полей
            if not feature_name:
                # Пробуем другие возможные поля
                feature_name = doc.metadata.get('name', '')
                if not feature_name:
                    # Пытаемся найти в page_content (описание может начинаться с названия)
                    text = doc.page_content or ""
                    # Ищем паттерн или берем первую строку
                    parts = text.split('\n')
                    for part in parts[:3]:  # Проверяем первые 3 строки
                        part = part.strip()
                        if part and len(part) < 100:  # Название обычно короткое
                            feature_name = part
                            break
            
            # Извлекаем описание
            feature_desc = doc.page_content if doc.page_content else ""
            if not feature_desc:
                feature_desc = doc.metadata.get('description', '')
            
            # Ограничиваем длину описания для промпта
            feature_desc = feature_desc[:1000] if feature_desc else ""
            
            if not feature_name:
                logger.warning(f"Не удалось извлечь feature_name из документа. Метаданные: {doc.metadata.keys()}")
                continue
            
            # Проверяем соответствие признака запросу
            if self.check_feature_match(user_query, feature_name, feature_desc):
                matched_features.append({
                    'feature_name': feature_name,
                    'description': feature_desc,
                    'doc': doc
                })
        
        if not matched_features:
            logger.warning("Не найдено признаков, соответствующих запросу")
            return pd.DataFrame(), "К сожалению, не найдено признаков, соответствующих вашему запросу."
        
        logger.info(f"Найдено {len(matched_features)} соответствующих признаков")
        
        # Шаг 4: Генерация и выполнение SQL запросов
        logger.info("ШАГ 4: Генерация и выполнение SQL запросов")
        all_results = []
        
        for feature_info in matched_features:
            feature_name = feature_info['feature_name']
            feature_desc = feature_info['description']
            
            # Генерируем SQL запрос
            sql_query = self.generate_sql_query(user_query, feature_name, feature_desc)
            
            if sql_query:
                # Выполняем SQL запрос
                result_df = self.execute_sql_query(sql_query)
                
                if not result_df.empty:
                    # Добавляем информацию о признаке
                    result_df['matched_feature'] = feature_name
                    all_results.append(result_df)
                    logger.info(f"Для признака '{feature_name}' найдено {len(result_df)} записей")
        
        # Объединяем все результаты
        if all_results:
            combined_results = pd.concat(all_results, ignore_index=True)
            logger.info(f"Всего найдено {len(combined_results)} записей")
        else:
            combined_results = pd.DataFrame()
            logger.warning("SQL запросы не вернули результатов")
        
        # Шаг 5: Генерация финального ответа
        logger.info("ШАГ 5: Генерация финального ответа преподавателя")
        final_answer = self.generate_final_summary(user_query, combined_results)
        
        return combined_results, final_answer
    
    def extract_coordinates(self, results_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Извлечение координат из результатов поиска для веб-интерфейса.
        
        Args:
            results_df: DataFrame с результатами поиска
            
        Returns:
            Список словарей с координатами: [{"lon": float, "lat": float, "info": str}, ...]
        """
        coordinates = []
        
        if results_df.empty:
            return coordinates
        
        if 'lon' in results_df.columns and 'lat' in results_df.columns:
            for idx, row in results_df.iterrows():
                lon = row.get('lon', None)
                lat = row.get('lat', None)
                
                if pd.notna(lon) and pd.notna(lat):
                    lon_str = str(lon).strip()
                    lat_str = str(lat).strip()
                    
                    # Обработка массивов координат
                    if lon_str.startswith('['):
                        try:
                            import ast
                            lon_array = ast.literal_eval(lon_str)
                            if isinstance(lon_array, list) and len(lon_array) > 0:
                                lon_val = float(lon_array[0])
                            else:
                                continue
                        except:
                            try:
                                lon_val = float(lon_str.strip('[]').split(',')[0].strip())
                            except:
                                continue
                    else:
                        try:
                            lon_val = float(lon_str)
                        except:
                            continue
                    
                    if lat_str.startswith('['):
                        try:
                            import ast
                            lat_array = ast.literal_eval(lat_str)
                            if isinstance(lat_array, list) and len(lat_array) > 0:
                                lat_val = float(lat_array[-1] if len(lat_array) > 1 else lat_array[0])
                            else:
                                continue
                        except:
                            try:
                                lat_val = float(lat_str.strip('[]').split(',')[-1].strip())
                            except:
                                continue
                    else:
                        try:
                            lat_val = float(lat_str)
                        except:
                            continue
                    
                    # Валидация координат
                    if -180 <= lon_val <= 180 and -90 <= lat_val <= 90:
                        # Собираем дополнительную информацию о записи
                        info_parts = []
                        for col in ['layer_name', 'Регион', 'Свита', 'Пласт', 'matched_feature']:
                            if col in row and pd.notna(row[col]):
                                info_parts.append(f"{col}: {row[col]}")
                        
                        info = ", ".join(info_parts) if info_parts else f"Запись {idx + 1}"
                        
                        coordinates.append({
                            "lon": lon_val,
                            "lat": lat_val,
                            "info": info
                        })
        
        return coordinates


def main():
    """Пример использования RAG системы."""
    
    # Конфигурация
    OPENSEARCH_HOST="155.212.191.208"
    OPENSEARCH_PORT=9200
    OPENSEARCH_USE_SSL=False  
    OPENSEARCH_VERIFY_CERTS=False
    OPENSEARCH_AUTH = ("admin", "admin")
    OPENSEARCH_INDEX_DESCRIPTIONS = "rag_descriptions"
    OPENSEARCH_INDEX_LAYERS = "rag_layers"
    
    # Инициализация RAG системы
    logger.info("Инициализация RAG системы...")
    rag_system = RAGSystemLangChain(
        opensearch_host=OPENSEARCH_HOST,
        opensearch_port=OPENSEARCH_PORT,
        opensearch_use_ssl=OPENSEARCH_USE_SSL,
        opensearch_verify_certs=OPENSEARCH_VERIFY_CERTS,
        opensearch_auth=OPENSEARCH_AUTH,
        opensearch_index_descriptions=OPENSEARCH_INDEX_DESCRIPTIONS,
        opensearch_index_layers=OPENSEARCH_INDEX_LAYERS,
        credentials=GIGACHAT_CREDENTIALS
    )
    
    # Примеры запросов
    test_queries = [
        "Где R0 больше 1.0%?"
        #"Где максимальное значение Сорг?"
    ]
    
    # Выполнение запросов
    for query in test_queries:
        logger.info(f"\n{'='*80}")
        logger.info(f"ОБРАБОТКА ЗАПРОСА: {query}")
        logger.info(f"{'='*80}\n")
        
        try:
            results, answer = rag_system.query(user_query=query, top_k=20)
            
            # Вывод ответа
            print("\n" + "="*80)
            print("ОТВЕТ ПРЕПОДАВАТЕЛЯ:")
            print("="*80)
            print(answer)
            print("="*80 + "\n")
            
            # Вывод статистики
            if not results.empty:
                print(f"Найдено результатов: {len(results)}")
                print(f"Колонки: {list(results.columns)[:10]}...")
            else:
                print("Результаты не найдены.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса '{query}': {e}", exc_info=True)


if __name__ == "__main__":
    main()

