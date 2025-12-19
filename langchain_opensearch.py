"""
Работа с OpenSearch через LangChain.

Примеры использования LangChain для работы с OpenSearch:
- Поиск документов
- Получение конкретного документа по ID
- Использование в RAG цепочках
"""

import logging
from typing import List, Dict, Optional, Any
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from opensearchpy import OpenSearch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LangChainOpenSearch:
    """
    Класс для работы с OpenSearch через LangChain.
    """
    
    def __init__(
        self,
        opensearch_host: str = "localhost",
        opensearch_port: int = 9200,
        opensearch_use_ssl: bool = False,
        opensearch_verify_certs: bool = False,
        opensearch_auth: Optional[tuple] = None,
        index_name: str = "rag_neft",
        embedding_model_name: str = "ai-forever/sbert_large_nlu_ru"
    ):
        """
        Инициализация LangChain OpenSearch.
        
        Args:
            opensearch_host: Хост OpenSearch
            opensearch_port: Порт OpenSearch
            opensearch_use_ssl: Использовать SSL
            opensearch_verify_certs: Проверять сертификаты
            opensearch_auth: Учетные данные (username, password)
            index_name: Имя индекса
            embedding_model_name: Название модели для эмбеддингов
        """
        self.index_name = index_name
        
        # Создание клиента OpenSearch
        self.opensearch_client = OpenSearch(
            hosts=[{'host': opensearch_host, 'port': opensearch_port}],
            http_auth=opensearch_auth,
            use_ssl=opensearch_use_ssl,
            verify_certs=opensearch_verify_certs,
            timeout=30
        )
        
        # Инициализация модели эмбеддингов
        logger.info(f"Загрузка модели эмбеддингов: {embedding_model_name}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model_name,
            model_kwargs={'device': 'cpu'}
        )
        
        # Создание векторного хранилища LangChain
        self.vector_store = OpenSearchVectorSearch(
            opensearch_url=f"{'https' if opensearch_use_ssl else 'http'}://{opensearch_host}:{opensearch_port}",
            index_name=index_name,
            embedding_function=self.embeddings,
            http_auth=opensearch_auth,
            use_ssl=opensearch_use_ssl,
            verify_certs=opensearch_verify_certs
        )
        
        logger.info(f"LangChain OpenSearch инициализирован для индекса: {index_name}")
    
    def search(
        self,
        query: str,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Поиск документов по запросу.
        
        Args:
            query: Текстовый запрос
            k: Количество результатов
            filter: Дополнительные фильтры
            
        Returns:
            Список найденных документов
        """
        logger.info(f"Поиск топ-{k} документов по запросу: '{query[:50]}...'")
        
        try:
            # Поиск через LangChain
            results = self.vector_store.similarity_search(
                query=query,
                k=k,
                filter=filter
            )
            
            logger.info(f"Найдено {len(results)} документов")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return []
    
    def search_with_score(
        self,
        query: str,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[tuple]:
        """
        Поиск документов с оценкой релевантности.
        
        Args:
            query: Текстовый запрос
            k: Количество результатов
            filter: Дополнительные фильтры
            
        Returns:
            Список кортежей (Document, score)
        """
        logger.info(f"Поиск с оценками топ-{k} документов по запросу: '{query[:50]}...'")
        
        try:
            # Поиск с оценками через LangChain
            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter
            )
            
            logger.info(f"Найдено {len(results)} документов")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка поиска с оценками: {e}")
            return []
    
    def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        Получение конкретного документа по ID.
        
        Args:
            doc_id: ID документа в OpenSearch
            
        Returns:
            Document или None, если не найден
        """
        logger.info(f"Получение документа по ID: {doc_id}")
        
        try:
            # Получение документа напрямую из OpenSearch
            response = self.opensearch_client.get(
                index=self.index_name,
                id=doc_id
            )
            
            if response['found']:
                source = response['_source']
                
                # Создание Document из источника
                # Извлекаем текст
                text = source.get('text', '')
                
                # Извлекаем метаданные (все остальные поля)
                metadata = {k: v for k, v in source.items() if k != 'text' and k != 'embedding'}
                metadata['_id'] = response['_id']
                metadata['_score'] = None  # Нет score для прямого получения
                
                doc = Document(page_content=text, metadata=metadata)
                
                logger.info(f"Документ найден: ID={doc_id}")
                return doc
            else:
                logger.warning(f"Документ с ID {doc_id} не найден")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения документа по ID {doc_id}: {e}")
            return None
    
    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Document]:
        """
        Получение нескольких документов по их ID.
        
        Args:
            doc_ids: Список ID документов
            
        Returns:
            Список найденных документов
        """
        logger.info(f"Получение {len(doc_ids)} документов по ID")
        
        documents = []
        for doc_id in doc_ids:
            doc = self.get_document_by_id(doc_id)
            if doc:
                documents.append(doc)
        
        logger.info(f"Получено {len(documents)} из {len(doc_ids)} документов")
        return documents
    
    def get_document_by_field(
        self,
        field_name: str,
        field_value: Any,
        limit: int = 10
    ) -> List[Document]:
        """
        Получение документов по значению поля.
        
        Args:
            field_name: Имя поля для поиска
            field_value: Значение поля
            limit: Максимальное количество результатов
            
        Returns:
            Список найденных документов
        """
        logger.info(f"Поиск документов по полю {field_name}={field_value}")
        
        try:
            # Поиск через OpenSearch
            query = {
                "query": {
                    "term": {
                        field_name: field_value
                    }
                },
                "size": limit
            }
            
            response = self.opensearch_client.search(
                index=self.index_name,
                body=query
            )
            
            documents = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                text = source.get('text', '')
                metadata = {k: v for k, v in source.items() if k != 'text' and k != 'embedding'}
                metadata['_id'] = hit['_id']
                metadata['_score'] = hit['_score']
                
                doc = Document(page_content=text, metadata=metadata)
                documents.append(doc)
            
            logger.info(f"Найдено {len(documents)} документов")
            return documents
            
        except Exception as e:
            logger.error(f"Ошибка поиска по полю: {e}")
            return []
    
    def get_all_documents(self, limit: int = 100) -> List[Document]:
        """
        Получение всех документов из индекса (с ограничением).
        
        Args:
            limit: Максимальное количество документов
            
        Returns:
            Список документов
        """
        logger.info(f"Получение всех документов (лимит: {limit})")
        
        try:
            query = {
                "query": {"match_all": {}},
                "size": limit
            }
            
            response = self.opensearch_client.search(
                index=self.index_name,
                body=query
            )
            
            documents = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                text = source.get('text', '')
                metadata = {k: v for k, v in source.items() if k != 'text' and k != 'embedding'}
                metadata['_id'] = hit['_id']
                metadata['_score'] = hit['_score']
                
                doc = Document(page_content=text, metadata=metadata)
                documents.append(doc)
            
            logger.info(f"Получено {len(documents)} документов")
            return documents
            
        except Exception as e:
            logger.error(f"Ошибка получения всех документов: {e}")
            return []


# Примеры использования
if __name__ == "__main__":
    # Конфигурация
    OPENSEARCH_HOST = "localhost"
    OPENSEARCH_PORT = 9200
    OPENSEARCH_USE_SSL = True
    OPENSEARCH_VERIFY_CERTS = False
    OPENSEARCH_AUTH = ("admin", "Rodion1killer")
    INDEX_NAME = "rag_descriptions"
    
    try:
        # Инициализация
        logger.info("Инициализация LangChain OpenSearch...")
        langchain_opensearch = LangChainOpenSearch(
            opensearch_host=OPENSEARCH_HOST,
            opensearch_port=OPENSEARCH_PORT,
            opensearch_use_ssl=OPENSEARCH_USE_SSL,
            opensearch_verify_certs=OPENSEARCH_VERIFY_CERTS,
            opensearch_auth=OPENSEARCH_AUTH,
            index_name=INDEX_NAME
        )
        
        
        print("ПРИМЕР 5: Получение нескольких документов по ID")
        print("="*80)
        
        # Пример 5: Получение нескольких документов по ID
        if len(results) >= 3:
            doc_ids = [doc.metadata.get('_id') for doc in results[:3] if doc.metadata.get('_id')]
            print(f"\nПолучение документов с ID: {doc_ids}")
            
            docs_by_ids = langchain_opensearch.get_documents_by_ids(doc_ids)
            
            print(f"Получено: {len(docs_by_ids)} документов")
            for i, doc in enumerate(docs_by_ids, 1):
                print(f"[{i}] ID: {doc.metadata.get('_id')}")
                print(f"    Текст: {doc.page_content[:100]}...")
                print()
        
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)

