"""
Интеграция RAG системы с OpenSearch для проекта "Цифровой Каспий".

Этот модуль предоставляет высокоуровневый API для:
- Индексации геологических данных
- Семантического поиска
- Генерации ответов с использованием LLM
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path

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

# Импорты LangChain с обработкой разных версий
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
    logger.warning("langchain_openai не установлен, LLM функции будут недоступны")

try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    try:
        from langchain.prompts import PromptTemplate
    except ImportError:
        PromptTemplate = None  # Будем использовать простую строковую форматировку
        logger.debug("PromptTemplate не найден, будет использоваться простая строковая форматировка")

from opensearch_manager import OpenSearchManager


class CaspianRAGSystem:
    """RAG система для работы с данными Каспийского региона."""
    
    def __init__(
        self,
        opensearch_host: Optional[str] = None,
        opensearch_port: Optional[int] = None,
        opensearch_auth: Optional[tuple] = None,
        opensearch_use_ssl: Optional[bool] = None,
        opensearch_verify_certs: Optional[bool] = None,
        openai_api_key: Optional[str] = None,
        embedding_model: Optional[str] = None,
        index_name: Optional[str] = None
    ):
        """
        Инициализация RAG системы.
        
        Args:
            opensearch_host: Хост OpenSearch (по умолчанию из OPENSEARCH_HOST или "localhost")
            opensearch_port: Порт OpenSearch (по умолчанию из OPENSEARCH_PORT или 9200)
            opensearch_auth: Аутентификация OpenSearch (username, password) или из OPENSEARCH_USERNAME/PASSWORD
            opensearch_use_ssl: Использовать SSL/HTTPS (None = автоопределение по порту или OPENSEARCH_USE_SSL)
            opensearch_verify_certs: Проверять SSL сертификаты (по умолчанию из OPENSEARCH_VERIFY_CERTS или True)
            openai_api_key: API ключ OpenAI (если None, используется из env)
            embedding_model: Модель для эмбеддингов
            index_name: Имя индекса в OpenSearch
        """
        # Чтение настроек из переменных окружения, если не указаны явно
        if opensearch_host is None:
            opensearch_host = os.getenv("OPENSEARCH_HOST", "localhost")
        
        if opensearch_port is None:
            opensearch_port = int(os.getenv("OPENSEARCH_PORT", "9200"))
        
        if opensearch_auth is None:
            username = os.getenv("OPENSEARCH_USERNAME")
            password = os.getenv("OPENSEARCH_PASSWORD")
            if username and password:
                opensearch_auth = (username, password)
        
        if opensearch_verify_certs is None:
            verify_env = os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower()
            opensearch_verify_certs = verify_env in ("true", "1", "yes")
        
        if embedding_model is None:
            embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
        if index_name is None:
            index_name = os.getenv("INDEX_NAME", "caspian_data")
        
        # OpenSearch менеджер (параметры загрузятся из .env автоматически, если не указаны)
        self.opensearch_manager = OpenSearchManager(
            host=opensearch_host,
            port=opensearch_port,
            http_auth=opensearch_auth,
            use_ssl=opensearch_use_ssl,
            verify_certs=opensearch_verify_certs,
            embedding_model=embedding_model
        )
        
        self.index_name = index_name
        
        # LLM для генерации ответов
        self.llm = None
        if ChatOpenAI and (openai_api_key or os.getenv("OPENAI_API_KEY")):
            try:
                self.llm = ChatOpenAI(
                    model_name="gpt-4",
                    temperature=0,
                    openai_api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
                )
                logger.info("LLM инициализирован")
            except Exception as e:
                logger.warning(f"Ошибка инициализации LLM: {e}")
                self.llm = None
        elif not ChatOpenAI:
            logger.warning("langchain_openai не установлен. Установите: pip install langchain-openai")
        else:
            logger.warning("OpenAI API ключ не найден. Генерация ответов будет недоступна.")
        
        # LangChain VectorStore
        self.vectorstore = None
        self._init_vectorstore()
    
    def _init_vectorstore(self):
        """Инициализация LangChain VectorStore."""
        try:
            self.vectorstore = self.opensearch_manager.get_langchain_vectorstore(
                self.index_name
            )
            logger.info("VectorStore инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации VectorStore: {e}")
    
    def index_data(self, df, batch_size: int = 100):
        """
        Индексация данных в OpenSearch.
        
        Args:
            df: DataFrame с данными
            batch_size: Размер батча
        """
        # Создание индекса если не существует
        if not self.opensearch_manager.client.indices.exists(index=self.index_name):
            logger.info(f"Создание индекса {self.index_name}")
            self.opensearch_manager.create_index(self.index_name)
        
        # Индексация данных
        self.opensearch_manager.index_dataframe(
            df,
            self.index_name,
            batch_size=batch_size,
            progress_callback=lambda c, t: logger.info(f"Индексация: {c}/{t}")
        )
    
    def search(self, query: str, top_k: int = 5, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Семантический поиск.
        
        Args:
            query: Текстовый запрос
            top_k: Количество результатов
            filters: Фильтры поиска
            
        Returns:
            Список результатов
        """
        return self.opensearch_manager.search(
            query,
            self.index_name,
            top_k=top_k,
            filter_dict=filters
        )
    
    def answer_question(
        self,
        question: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
        return_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Ответ на вопрос с использованием RAG.
        
        Args:
            question: Вопрос пользователя
            top_k: Количество документов для контекста
            filters: Фильтры поиска
            return_sources: Возвращать ли источники
            
        Returns:
            Словарь с ответом и источниками
        """
        if not self.llm:
            # Если LLM недоступен, возвращаем только результаты поиска
            results = self.search(question, top_k=top_k, filters=filters)
            return {
                "answer": "LLM недоступен. Вот результаты поиска:",
                "sources": results,
                "llm_available": False
            }
        
        # Поиск релевантных документов
        results = self.search(question, top_k=top_k, filters=filters)
        
        if not results:
            return {
                "answer": "Не найдено релевантной информации.",
                "sources": [],
                "llm_available": True
            }
        
        # Формирование контекста
        context = "\n\n".join([
            f"Документ {i+1} (слой: {r['layer']}, релевантность: {r['score']:.3f}):\n{r['text']}"
            for i, r in enumerate(results)
        ])
        
        # Промпт для LLM
        prompt_template = """Ты эксперт по геологии и нефтегазовой отрасли Каспийского региона.
Используй предоставленный контекст для ответа на вопрос. Если в контексте нет информации,
скажи об этом честно.

Контекст:
{context}

Вопрос: {question}

Ответ (на русском языке, подробно и профессионально):"""
        
        # Форматирование промпта
        if PromptTemplate:
            try:
                prompt = PromptTemplate(
                    template=prompt_template,
                    input_variables=["context", "question"]
                )
                formatted_prompt = prompt.format(context=context, question=question)
            except Exception as e:
                logger.warning(f"Ошибка создания PromptTemplate: {e}, используем простую форматировку")
                formatted_prompt = prompt_template.format(context=context, question=question)
        else:
            formatted_prompt = prompt_template.format(context=context, question=question)
        
        # Генерация ответа
        try:
            # Используем актуальный API LangChain
            if hasattr(self.llm, 'invoke'):
                # Новый API (LangChain >= 0.1.0)
                response = self.llm.invoke(formatted_prompt)
                answer = response.content if hasattr(response, 'content') else str(response)
            elif hasattr(self.llm, 'call'):
                # Альтернативный API
                answer = self.llm.call(formatted_prompt)
            elif hasattr(self.llm, 'predict'):
                # Старый API (LangChain < 0.1.0)
                answer = self.llm.predict(formatted_prompt)
            else:
                # Последняя попытка - прямой вызов
                answer = str(self.llm(formatted_prompt))
            
            result = {
                "answer": answer,
                "sources": results if return_sources else [],
                "llm_available": True
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return {
                "answer": f"Ошибка генерации ответа: {str(e)}",
                "sources": results if return_sources else [],
                "llm_available": True,
                "error": str(e)
            }
    
    def get_statistics(self) -> Dict:
        """Получение статистики системы."""
        stats = self.opensearch_manager.get_index_stats(self.index_name)
        return {
            "index_name": self.index_name,
            "index_stats": stats,
            "llm_available": self.llm is not None,
            "vectorstore_available": self.vectorstore is not None
        }


# Пример использования
if __name__ == "__main__":
    import pandas as pd
    
    # Инициализация системы для HTTPS
    # Вариант 1: Явное указание параметров
    rag = CaspianRAGSystem(
        opensearch_host="localhost",
        opensearch_port=9200,  # Или 443 для стандартного HTTPS
        opensearch_use_ssl=True,  # Включить HTTPS
        opensearch_verify_certs=False,  # Проверять сертификаты (False для самоподписанных)
        opensearch_auth=("admin", "Rodion1killer"),  # Если требуется аутентификация
        index_name="caspian_data"
    )
    
    # Вариант 2: Через переменные окружения (см. HTTPS_SETUP.md)
    # rag = CaspianRAGSystem(index_name="caspian_data")
    
    # Проверка подключения
    if not rag.opensearch_manager.check_connection():
        print("Не удалось подключиться к OpenSearch")
        exit(1)
    
    # Загрузка и индексация данных (если еще не проиндексировано)
    if not rag.opensearch_manager.client.indices.exists(index="caspian_data"):
        print("Загрузка данных...")
        df = pd.read_csv("ЦК(25.06.25)/pars_test.csv")
        print(f"Индексация {len(df)} строк...")
        rag.index_data(df.head(1000))  # Первые 1000 для примера
    
    # Примеры вопросов
    questions = [
        "Какие месторождения нефти есть в регионе?",
        "Где находятся грязевые вулканы?",
        "Какая толщина эоценовых отложений?",
        "Какие геологические структуры присутствуют?"
    ]
    
    print("\n" + "="*80)
    print("RAG СИСТЕМА - ДЕМОНСТРАЦИЯ")
    print("="*80 + "\n")
    
    for question in questions:
        print(f"Вопрос: {question}")
        print("-" * 80)
        
        result = rag.answer_question(question, top_k=3)
        
        print(f"Ответ: {result['answer']}")
        print(f"\nНайдено источников: {len(result['sources'])}")
        if result['sources']:
            print("\nТоп-3 источника:")
            for i, source in enumerate(result['sources'][:3], 1):
                print(f"  {i}. Слой: {source['layer']}, Релевантность: {source['score']:.4f}")
                print(f"     {source['text'][:150]}...")
        print("\n" + "="*80 + "\n")
    
    # Статистика
    stats = rag.get_statistics()
    print("Статистика системы:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

