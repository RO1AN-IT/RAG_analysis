"""
Простая RAG система для получения топ-k релевантных данных по запросу пользователя.

Использует векторный поиск через OpenSearch для семантического поиска.
"""

import logging
import pandas as pd
from typing import List, Dict, Optional, Tuple
from opensearch_test import OpenSearchManager, GIGACHAT_CREDENTIALS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleRAG:
    """
    Простая RAG система для поиска топ-k релевантных документов.
    
    Использует векторный поиск через OpenSearch для семантического поиска.
    """
    
    def __init__(
        self,
        opensearch_host: str = "localhost",
        opensearch_port: int = 9200,
        opensearch_use_ssl: bool = False,
        opensearch_verify_certs: bool = False,
        opensearch_auth: Optional[Tuple[str, str]] = None,
        index_name: str = "rag_neft",
        embedding_model: str = "ai-forever/sbert_large_nlu_ru"
    ):
        """
        Инициализация RAG системы.
        
        Args:
            opensearch_host: Хост OpenSearch
            opensearch_port: Порт OpenSearch
            opensearch_use_ssl: Использовать SSL
            opensearch_verify_certs: Проверять сертификаты
            opensearch_auth: Учетные данные (username, password)
            index_name: Имя индекса в OpenSearch
            embedding_model: Модель для эмбеддингов
        """
        self.index_name = index_name
        
        # Инициализация OpenSearch
        logger.info(f"Инициализация OpenSearch: {opensearch_host}:{opensearch_port}")
        self.opensearch_manager = OpenSearchManager(
            host=opensearch_host,
            port=opensearch_port,
            use_ssl=opensearch_use_ssl,
            verify_certs=opensearch_verify_certs,
            http_auth=opensearch_auth,
            embedding_model=embedding_model
        )
        
        # Проверка подключения
        if not self.opensearch_manager.check_connection():
            raise ConnectionError("Не удалось подключиться к OpenSearch")
        
        # Проверка существования индекса
        if not self.opensearch_manager.client.indices.exists(index=index_name):
            raise ValueError(f"Индекс {index_name} не существует. Создайте его сначала.")
        
        logger.info("RAG система инициализирована успешно")
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, any]] = None,
        min_score: float = 0.0
    ) -> pd.DataFrame:
        """
        Поиск топ-k релевантных документов по запросу.
        
        Args:
            query: Текстовый запрос пользователя
            top_k: Количество релевантных документов для возврата
            filters: Дополнительные фильтры (например, {"region": "Южный Каспий"})
            min_score: Минимальный score для включения в результаты
            
        Returns:
            DataFrame с топ-k релевантными документами, отсортированными по релевантности
        """
        logger.info(f"Поиск топ-{top_k} релевантных документов по запросу: '{query[:50]}...'")
        
        # Выполнение векторного поиска
        results = self.opensearch_manager.search(
            query_text=query,
            index_name=self.index_name,
            top_k=top_k,
            filters=filters
        )
        
        if not results:
            logger.warning("Поиск не вернул результатов")
            return pd.DataFrame()
        
        # Преобразование в DataFrame
        df = pd.DataFrame(results)
        
        # Фильтрация по минимальному score
        if '_score' in df.columns:
            df = df[df['_score'] >= min_score]
            # Сортировка по score (по убыванию)
            df = df.sort_values('_score', ascending=False)
        
        # Ограничение до top_k
        df = df.head(top_k)
        
        logger.info(f"Найдено {len(df)} релевантных документов")
        
        return df
    
    def get_relevant_data(
        self,
        user_query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, any]] = None,
        return_text_only: bool = False
    ) -> Tuple[pd.DataFrame, List[Dict[str, any]]]:
        """
        Получение топ-k релевантных данных по запросу пользователя.
        
        Args:
            user_query: Запрос пользователя
            top_k: Количество релевантных документов
            filters: Дополнительные фильтры
            return_text_only: Если True, возвращает только текстовые поля
            
        Returns:
            Tuple[DataFrame с данными, Список словарей с результатами]
        """
        # Поиск релевантных документов
        df = self.search(
            query=user_query,
            top_k=top_k,
            filters=filters
        )
        
        if df.empty:
            logger.warning("Релевантные данные не найдены")
            return pd.DataFrame(), []
        
        # Если нужны только текстовые поля
        if return_text_only:
            text_columns = ['text', 'layer_name', 'description', 'content']
            available_text_cols = [col for col in text_columns if col in df.columns]
            if available_text_cols:
                df = df[available_text_cols]
        
        # Преобразование в список словарей
        results_list = df.to_dict('records')
        
        return df, results_list
    
    def get_top_k(
        self,
        query: str,
        k: int = 10,
        filters: Optional[Dict[str, any]] = None
    ) -> List[Dict[str, any]]:
        """
        Простой метод для получения топ-k результатов.
        
        Args:
            query: Запрос пользователя
            k: Количество результатов
            filters: Дополнительные фильтры
            
        Returns:
            Список словарей с топ-k релевантными документами
        """
        _, results = self.get_relevant_data(
            user_query=query,
            top_k=k,
            filters=filters
        )
        return results


# Пример использования
if __name__ == "__main__":
    # Конфигурация
    OPENSEARCH_HOST = "localhost"
    OPENSEARCH_PORT = 9200
    OPENSEARCH_AUTH = ("admin", "Rodion1killer")  # Замените на свои данные
    INDEX_NAME = "rag_neft"
    
    try:
        # Инициализация RAG системы
        logger.info("Инициализация RAG системы...")
        rag = SimpleRAG(
            opensearch_host=OPENSEARCH_HOST,
            opensearch_port=OPENSEARCH_PORT,
            opensearch_auth=OPENSEARCH_AUTH,
            index_name=INDEX_NAME
        )
        
        # Примеры запросов
        queries = [
            "зрелая нефть R0",
            "геологические слои Каспийского моря",
            "глубина залегания пластов",
        ]
        
        for query in queries:
            logger.info(f"\n{'='*80}")
            logger.info(f"Запрос: {query}")
            logger.info(f"{'='*80}\n")
            
            # Получение топ-5 релевантных документов
            results = rag.get_top_k(query, k=5)
            
            print(f"Найдено результатов: {len(results)}\n")
            
            for i, result in enumerate(results, 1):
                print(f"Результат {i}:")
                print(f"  Score: {result.get('_score', 'N/A')}")
                
                # Вывод текстового содержимого
                if 'text' in result:
                    text_preview = result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
                    print(f"  Текст: {text_preview}")
                
                '''
                # Вывод других важных полей
                for key in ['layer_name', 'region', 'depth', 'R0', 'Corg']:
                    if key in result and result[key]:
                        print(f"  {key}: {result[key]}")
                '''
                
                print()
            
            print("-"*80 + "\n")
            
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)

