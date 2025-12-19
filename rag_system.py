"""
RAG система для поиска релевантных данных из базы геологических данных Каспийского моря.

Объединяет:
1. Векторный поиск через OpenSearch (семантический поиск)
2. SQL запросы через CSVSQLEngine (структурированные запросы)
3. Генерацию ответов через GigaChat
"""

import logging
import pandas as pd
from typing import List, Dict, Optional, Tuple, Any
from opensearch_test import OpenSearchManager, CSVSQLEngine, GIGACHAT_CREDENTIALS
from gigachat import GigaChat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGSystem:
    """
    Комплексная RAG система для работы с геологическими данными.
    
    Поддерживает два режима поиска:
    1. Векторный поиск (OpenSearch) - для семантического поиска по тексту
    2. SQL запросы (CSVSQLEngine) - для структурированных запросов с условиями
    """
    
    def __init__(
        self,
        csv_path: str,
        opensearch_config: Optional[Dict[str, Any]] = None,
        opensearch_index: Optional[str] = None,
        use_opensearch: bool = True,
        credentials: str = GIGACHAT_CREDENTIALS
    ):
        """
        Инициализация RAG системы.
        
        Args:
            csv_path: Путь к CSV файлу с данными
            opensearch_config: Конфигурация OpenSearch (host, port, use_ssl, verify_certs, http_auth)
            opensearch_index: Имя индекса OpenSearch (если используется)
            use_opensearch: Использовать ли OpenSearch для векторного поиска
            credentials: Учетные данные GigaChat
        """
        self.csv_path = csv_path
        self.credentials = credentials
        self.use_opensearch = use_opensearch
        
        # Инициализация SQL движка (всегда используется)
        logger.info("Инициализация CSVSQLEngine...")
        self.sql_engine = CSVSQLEngine(
            csv_path=csv_path,
            credentials=credentials
        )
        
        # Инициализация OpenSearch (опционально)
        self.opensearch_manager = None
        self.opensearch_index = opensearch_index
        
        if use_opensearch and opensearch_config:
            try:
                logger.info("Инициализация OpenSearchManager...")
                self.opensearch_manager = OpenSearchManager(
                    host=opensearch_config.get('host'),
                    port=opensearch_config.get('port'),
                    use_ssl=opensearch_config.get('use_ssl', False),
                    verify_certs=opensearch_config.get('verify_certs', False),
                    http_auth=opensearch_config.get('http_auth'),
                    embedding_model=opensearch_config.get('embedding_model')
                )
                
                # Проверка подключения
                if not self.opensearch_manager.check_connection():
                    logger.warning("Не удалось подключиться к OpenSearch. Векторный поиск будет отключен.")
                    self.use_opensearch = False
                    self.opensearch_manager = None
                else:
                    logger.info("OpenSearch подключен успешно")
            except Exception as e:
                logger.warning(f"Ошибка инициализации OpenSearch: {e}. Векторный поиск будет отключен.")
                self.use_opensearch = False
                self.opensearch_manager = None
        
        # Промпт для определения типа запроса
        self.query_classification_prompt = """Ты - эксперт по анализу запросов к геологической базе данных.

Определи тип запроса пользователя:

1. СТРУКТУРИРОВАННЫЙ ЗАПРОС - запрос с конкретными условиями, фильтрами, числовыми значениями:
   - Примеры: "Где R0 > 1.0%?", "Найди все записи с глубиной больше 1000 метров", 
     "Покажи максимальное значение Сорг в регионе Южный Каспий"
   - Характеристики: содержит операторы сравнения (> < = >= <=), конкретные числа, названия полей

2. СЕМАНТИЧЕСКИЙ ЗАПРОС - запрос на поиск информации по смыслу, без конкретных условий:
   - Примеры: "Расскажи о зрелой нефти", "Что такое R0?", "Информация о геологических слоях",
     "Какие данные есть о нефтегазоносности?"
   - Характеристики: общие вопросы, поиск информации, объяснения понятий

3. КОМБИНИРОВАННЫЙ - содержит и структурированные условия, и семантический поиск

Запрос пользователя: "{user_query}"

Верни ТОЛЬКО одно слово: STRUCTURED, SEMANTIC или COMBINED"""

        # Промпт для генерации финального ответа с учетом всех источников
        self.final_answer_prompt_template = """Ты - эксперт-геолог, специализирующийся на анализе данных Каспийского моря и нефтегазовой геологии.

Пользователь задал вопрос: "{user_query}"

Данные из базы данных:

{retrieved_data}

СТРОГИЕ ТРЕБОВАНИЯ К ОТВЕТУ:

1. ОБЯЗАТЕЛЬНО начни с прямого ответа на вопрос пользователя (1-2 предложения)

2. КРИТИЧЕСКИ ВАЖНО - ОБЯЗАТЕЛЬНО включи координаты, если они есть в данных:
   - Формат: "📍 КООРДИНАТЫ: Долгота: [значение], Широта: [значение]"
   - Если координат несколько мест, перечисли ВСЕ
   - НЕ ПРОПУСКАЙ координаты ни при каких обстоятельствах!

3. Структурируй ответ:
   - Выдели ключевую информацию (максимальные/минимальные значения, регионы, глубины и т.д.)
   - Используй маркированные списки для перечисления
   - Выделяй важные числа жирным текстом (**число**)

4. Будь конкретным и информативным:
   - Используй точные значения из данных
   - Указывай регионы, свиты, пласты, если они есть
   - Объясняй геологический контекст, если это уместно

5. Если данных недостаточно для полного ответа, честно об этом скажи и предложи уточнить запрос

6. ПРОВЕРЬ перед отправкой: координаты ДОЛЖНЫ быть в ответе, если они есть в данных!

Верни ТОЛЬКО отформатированный ответ без дополнительных комментариев."""

    def classify_query(self, user_query: str) -> str:
        """
        Классификация типа запроса пользователя.
        
        Args:
            user_query: Запрос пользователя
            
        Returns:
            Тип запроса: 'STRUCTURED', 'SEMANTIC' или 'COMBINED'
        """
        prompt = self.query_classification_prompt.format(user_query=user_query)
        
        try:
            with GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False
            ) as giga:
                response = giga.chat(prompt)
                query_type = response.choices[0].message.content.strip().upper()
                
                # Нормализация ответа
                if 'STRUCTURED' in query_type:
                    return 'STRUCTURED'
                elif 'SEMANTIC' in query_type:
                    return 'SEMANTIC'
                elif 'COMBINED' in query_type:
                    return 'COMBINED'
                else:
                    # По умолчанию считаем структурированным, если есть числа и операторы
                    if any(op in user_query for op in ['>', '<', '=', '>=', '<=']) or any(char.isdigit() for char in user_query):
                        return 'STRUCTURED'
                    return 'SEMANTIC'
        except Exception as e:
            logger.error(f"Ошибка классификации запроса: {e}")
            # Эвристическая классификация
            if any(op in user_query for op in ['>', '<', '=', '>=', '<=']) or any(char.isdigit() for char in user_query):
                return 'STRUCTURED'
            return 'SEMANTIC'

    def vector_search(self, query: str, top_k: int = 10) -> pd.DataFrame:
        """
        Векторный поиск через OpenSearch.
        
        Args:
            query: Текстовый запрос
            top_k: Количество результатов
            
        Returns:
            DataFrame с результатами поиска
        """
        if not self.use_opensearch or not self.opensearch_manager or not self.opensearch_index:
            logger.warning("Векторный поиск недоступен (OpenSearch не настроен)")
            return pd.DataFrame()
        
        try:
            # Использование метода search из OpenSearchManager
            results = self.opensearch_manager.search(
                query_text=query,
                index_name=self.opensearch_index,
                top_k=top_k
            )
            
            if results:
                df = pd.DataFrame(results)
                logger.info(f"Векторный поиск вернул {len(df)} результатов")
                return df
            else:
                logger.info("Векторный поиск не вернул результатов")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Ошибка векторного поиска: {e}")
            return pd.DataFrame()

    def query(
        self,
        user_query: str,
        use_vector_search: bool = True,
        use_sql_search: bool = True,
        top_k_vector: int = 10,
        format_output: bool = True
    ) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Выполнение запроса пользователя с использованием RAG системы.
        
        Args:
            user_query: Запрос пользователя
            use_vector_search: Использовать ли векторный поиск
            use_sql_search: Использовать ли SQL поиск
            top_k_vector: Количество результатов векторного поиска
            format_output: Форматировать ли ответ через GigaChat
            
        Returns:
            Tuple[DataFrame с результатами, Отформатированный ответ]
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"RAG ЗАПРОС: {user_query}")
        logger.info(f"{'='*80}\n")
        
        # Классификация запроса
        query_type = self.classify_query(user_query)
        logger.info(f"Тип запроса: {query_type}")
        
        # Сбор результатов из разных источников
        all_results = []
        result_sources = []
        
        # 1. Векторный поиск (если включен и запрос семантический или комбинированный)
        if use_vector_search and self.use_opensearch and query_type in ['SEMANTIC', 'COMBINED']:
            logger.info("Выполнение векторного поиска...")
            vector_results = self.vector_search(user_query, top_k=top_k_vector)
            if not vector_results.empty:
                all_results.append(vector_results)
                result_sources.append("векторный поиск")
                logger.info(f"Векторный поиск: найдено {len(vector_results)} результатов")
        
        # 2. SQL поиск (если включен и запрос структурированный или комбинированный)
        if use_sql_search and query_type in ['STRUCTURED', 'COMBINED']:
            logger.info("Выполнение SQL запроса...")
            try:
                sql_results, _ = self.sql_engine.query(user_query, format_output=False)
                if not sql_results.empty:
                    all_results.append(sql_results)
                    result_sources.append("SQL запрос")
                    logger.info(f"SQL запрос: найдено {len(sql_results)} результатов")
            except Exception as e:
                logger.warning(f"Ошибка SQL запроса: {e}")
                # Если SQL не сработал, пробуем векторный поиск как запасной вариант
                if not all_results and use_vector_search and self.use_opensearch:
                    logger.info("SQL не сработал, пробуем векторный поиск...")
                    vector_results = self.vector_search(user_query, top_k=top_k_vector)
                    if not vector_results.empty:
                        all_results.append(vector_results)
                        result_sources.append("векторный поиск (запасной)")
        
        # Если ничего не найдено, пробуем альтернативный подход
        if not all_results:
            logger.warning("Основные методы не вернули результатов, пробуем альтернативные...")
            if query_type == 'SEMANTIC' and use_sql_search:
                # Для семантических запросов пробуем SQL с общим поиском
                try:
                    sql_results, _ = self.sql_engine.query(user_query, format_output=False)
                    if not sql_results.empty:
                        all_results.append(sql_results)
                        result_sources.append("SQL запрос (альтернативный)")
                except:
                    pass
            elif query_type == 'STRUCTURED' and use_vector_search and self.use_opensearch:
                # Для структурированных запросов пробуем векторный поиск
                vector_results = self.vector_search(user_query, top_k=top_k_vector)
                if not vector_results.empty:
                    all_results.append(vector_results)
                    result_sources.append("векторный поиск (альтернативный)")
        
        # Объединение результатов
        if all_results:
            # Объединяем все результаты, убирая дубликаты по ключевым полям
            combined_df = pd.concat(all_results, ignore_index=True)
            
            # Удаление дубликатов (если есть общие колонки)
            common_cols = ['lon', 'lat', 'layer_name', 'id']
            available_cols = [col for col in common_cols if col in combined_df.columns]
            if available_cols:
                combined_df = combined_df.drop_duplicates(subset=available_cols, keep='first')
            
            logger.info(f"Объединено результатов: {len(combined_df)} из источников: {', '.join(result_sources)}")
        else:
            combined_df = pd.DataFrame()
            logger.warning("Не найдено результатов ни одним методом")
        
        # Генерация финального ответа
        formatted_response = None
        if format_output:
            formatted_response = self.generate_final_answer(user_query, combined_df, result_sources)
        
        return combined_df, formatted_response

    def generate_final_answer(
        self,
        user_query: str,
        results_df: pd.DataFrame,
        sources: List[str]
    ) -> str:
        """
        Генерация финального ответа на основе всех найденных данных.
        
        Args:
            user_query: Исходный запрос пользователя
            results_df: DataFrame с результатами поиска
            sources: Список источников данных
            
        Returns:
            Отформатированный ответ
        """
        if results_df.empty:
            no_data_prompt = f"""Пользователь задал вопрос: "{user_query}"

По запросу данные в базе не найдены.

Объясни возможные причины и предложи альтернативные варианты поиска."""
            
            try:
                with GigaChat(
                    credentials=self.credentials,
                    verify_ssl_certs=False
                ) as giga:
                    response = giga.chat(no_data_prompt)
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"Ошибка генерации ответа: {e}")
                return "К сожалению, по вашему запросу данные в базе не найдены. Попробуйте уточнить параметры поиска."
        
        # Подготовка данных для промпта
        data_summary = results_df.to_string(index=False)
        
        # Извлечение координат
        coords_section = ""
        coords_list = []
        
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
                        coords_list.append(f"Место {idx + 1}: Долгота: {lon_str}, Широта: {lat_str}")
            
            if coords_list:
                coords_section = "\n\n" + "="*60 + "\nКООРДИНАТЫ НАЙДЕННЫХ МЕСТ:\n" + "="*60 + "\n" + "\n".join(coords_list) + "\n" + "="*60
        
        # Информация об источниках
        sources_info = f"\n\nИсточники данных: {', '.join(sources)}"
        
        # Формирование промпта
        prompt = self.final_answer_prompt_template.format(
            user_query=user_query,
            retrieved_data=data_summary + coords_section + sources_info
        )
        
        try:
            with GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False
            ) as giga:
                response = giga.chat(prompt)
                answer = response.choices[0].message.content.strip()
                
                # Проверка наличия координат в ответе
                if coords_list and 'координат' not in answer.lower() and '📍' not in answer:
                    logger.warning("Координаты не включены в ответ, добавляем принудительно")
                    coords_text = "\n\n📍 КООРДИНАТЫ:\n" + "\n".join([line.replace("Место ", "• ") for line in coords_list])
                    answer += coords_text
                
                return answer
        except Exception as e:
            logger.error(f"Ошибка генерации финального ответа: {e}")
            # Возвращаем базовый формат
            fallback = f"Найдено результатов: {len(results_df)}\n\n{data_summary}"
            if coords_section:
                fallback += coords_section
            return fallback


if __name__ == "__main__":
    # Конфигурация
    CSV_PATH = "/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/parsed_layers.csv"
    
    # Конфигурация OpenSearch (опционально)
    OPENSEARCH_CONFIG = {
        'host': "localhost",
        'port': 9200,
        'use_ssl': False,
        'verify_certs': False,
        'http_auth': ("admin", "Rodion1killer"),  # Если требуется
        'embedding_model': "ai-forever/sbert_large_nlu_ru"
    }
    OPENSEARCH_INDEX = "rag_neft"  # Имя индекса в OpenSearch
    
    # Инициализация RAG системы
    logger.info("Инициализация RAG системы...")
    rag_system = RAGSystem(
        csv_path=CSV_PATH,
        opensearch_config=OPENSEARCH_CONFIG,
        opensearch_index=OPENSEARCH_INDEX,
        use_opensearch=True,  # Установите False, если не используете OpenSearch
        credentials=GIGACHAT_CREDENTIALS
    )
    
    # Примеры запросов
    test_queries = [
        "Где R0 > 1.0% (зрелая нефть)?",
        "Расскажи о геологических слоях Каспийского моря",
        "Какие данные есть о глубине залегания пластов?",
        "Найди максимальное значение Сорг в регионе Южный Каспий"
    ]
    
    # Выполнение запросов
    for query in test_queries:
        logger.info(f"\n{'='*80}")
        logger.info(f"ОБРАБОТКА ЗАПРОСА: {query}")
        logger.info(f"{'='*80}\n")
        
        try:
            results, answer = rag_system.query(
                user_query=query,
                use_vector_search=True,
                use_sql_search=True,
                top_k_vector=10,
                format_output=True
            )
            
            # Вывод ответа
            if answer:
                print("\n" + "="*80)
                print("ОТВЕТ:")
                print("="*80)
                print(answer)
                print("="*80 + "\n")
            
            # Вывод статистики
            if not results.empty:
                print(f"Найдено результатов: {len(results)}")
                print(f"Колонки: {list(results.columns)[:10]}...")  # Первые 10 колонок
            else:
                print("Результаты не найдены.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса '{query}': {e}", exc_info=True)

