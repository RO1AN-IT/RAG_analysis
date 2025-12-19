from opensearchpy import OpenSearch, helpers
import os
import json
import logging
import re
from typing import List, Dict, Optional, Any, Tuple
import pandas as pd
from sentence_transformers import SentenceTransformer
from gigachat import GigaChat

# Инициализация логирования перед использованием
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Попытка импортировать DuckDB (предпочтительно) или pandasql (запасной вариант)
USE_DUCKDB = False
try:
    import duckdb
    USE_DUCKDB = True
    logger.info("Используется DuckDB для выполнения SQL запросов")
except ImportError:
    try:
        from pandasql import sqldf
        USE_DUCKDB = False
        logger.warning("DuckDB не установлен, используется pandasql. Рекомендуется установить DuckDB: pip install duckdb")
    except ImportError:
        logger.error("Необходимо установить либо DuckDB (pip install duckdb), либо pandasql (pip install pandasql)")
        raise ImportError("Необходимо установить либо DuckDB (pip install duckdb), либо pandasql (pip install pandasql)")

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


class CSVSQLEngine:
    """
    Класс для выполнения SQL запросов к CSV файлам с использованием GigaChat
    для формализации запросов и генерации SQL.
    """
    
    def __init__(self, csv_path: str, credentials: str):
        """
        Инициализация движка SQL для CSV.
        
        Args:
            csv_path: Путь к CSV файлу
            credentials: Учетные данные для GigaChat
        """
        self.csv_path = csv_path
        self.credentials = credentials
        self.df = None
        self._load_csv()
        
        # Жесткий промпт для формализации запроса пользователя
        self.formalization_prompt = """Ты - эксперт по формализации запросов к базе данных геологических слоев Каспийского моря.

Твоя задача - преобразовать естественный запрос пользователя в структурированный формализованный запрос.

Доступные поля в базе данных:
- layer_name: название слоя
- layer_path: путь к слою
- layer_type: тип слоя
- geometry_type: тип геометрии (Point, LineString, MultiLineString, Polygon и т.д.)
- lon, lat: координаты
- Регион: регион Каспийского моря
- Глубина, "Глубина,м": глубина в метрах
- ГАУС: геологическая активная система
- Литология: тип литологии
- Возраст: геологический возраст
- Система: геологическая система
- Свита: геологическая свита
- Пласт: название пласта
- Фация: тип фации
- Обстановка: геологическая обстановка
- Мощность: мощность слоя
- Сорг, "Сорг,%": содержание органического углерода (числовое значение в процентах)
- R0, "Rо,%": отражательная способность (числовое значение в процентах, например 1.0 означает 1.0%)
- "Тпл, С": температура пласта (числовое значение в градусах Цельсия)
- "P пл,МПа": давление пласта (числовое значение в МПа)
- Тип флюида: тип флюида
- Источник: источник данных
- И многие другие геологические и геофизические параметры

ВАЖНО для числовых условий:
- Если пользователь пишет "R0 > 1.0%", это означает условие WHERE "Rо,%" > 1.0 (без символа % в SQL)
- Проценты в запросе пользователя нужно преобразовать в числовое значение для сравнения
- Используй колонку "Rо,%" для R0, "Сорг,%" для Сорг и т.д.

Формализуй запрос пользователя, выделив:
1. Какие поля нужно выбрать (SELECT)
2. Какие условия фильтрации применить (WHERE) - ОБЯЗАТЕЛЬНО укажи точные имена колонок и числовые значения БЕЗ символа %
3. Какие группировки нужны (GROUP BY)
4. Какие сортировки нужны (ORDER BY)
5. Ограничения количества результатов (LIMIT)

Верни только формализованный запрос без дополнительных объяснений."""

        # Жесткий промпт для генерации SQL запроса
        self.sql_generation_prompt_template = """Ты - эксперт по написанию SQL запросов для работы с CSV файлами через DuckDB (или pandasql).

Ты работаешь с таблицей 'df', которая содержит данные о геологических слоях Каспийского моря.

Формализованный запрос пользователя:
{formalized_query}

Структура таблицы df (доступные колонки):
{columns_info}

КРИТИЧЕСКИ ВАЖНО - ПРОЧТИ ВНИМАТЕЛЬНО:
1. НИКОГДА не переводи имена колонок на английский! Используй ТОЛЬКО русские имена из списка выше
2. НЕ используй: "Region" (правильно: "Регион"), "Swit" (правильно: "Свита"), "Plast" (правильно: "Пласт")
3. КОПИРУЙ имена колонок ТОЧНО из списка выше - буква в букву, включая пробелы, запятые и специальные символы
4. Имена колонок с пробелами, запятыми или специальными символами ОБЯЗАТЕЛЬНО заключай в двойные кавычки: "Глубина,м" или "Регион"
5. Для строковых значений используй одинарные кавычки: 'значение'
6. Будь внимателен к типам данных: числовые поля сравнивай как числа, строковые как строки
7. Если в запросе упоминается поиск по тексту, используй оператор LIKE: "Регион" LIKE '%Южный%'
8. КРИТИЧЕСКИ ВАЖНО для числовых условий с процентами:
   - Если пользователь пишет "R0 > 1.0%" или "R0 > 1.0", используй колонку "Rо,%" и сравнивай с числом БЕЗ символа %: "Rо,%" > 1.0
   - Если пользователь пишет "Сорг > 5%", используй колонку "Сорг,%" и сравнивай: "Сорг,%" > 5
   - Проценты в запросе пользователя - это просто единица измерения, в SQL используй только число
   - Всегда проверяй на NULL: "Rо,%" > 1.0 AND "Rо,%" IS NOT NULL
8. Верни ТОЛЬКО SQL запрос без дополнительных комментариев и объяснений
9. Начинай запрос с SELECT и используй имя таблицы 'df'
10. Если колонка имеет суффикс _dup1, _dup2 и т.д., используй это имя полностью
11. Используй стандартный SQL синтаксис, совместимый с DuckDB/SQLite

ПРАВИЛЬНЫЕ примеры (обрати внимание на русские имена и числовые условия):
- SELECT "layer_name", "Регион", "Глубина,м", "lon", "lat" FROM df WHERE "Глубина,м" > 1000 LIMIT 10
- SELECT * FROM df WHERE "Регион" LIKE '%Южный%' AND "ГАУС" IS NOT NULL
- SELECT "layer_name", COUNT(*) as count FROM df GROUP BY "layer_name" ORDER BY count DESC LIMIT 20
- SELECT MAX("Cорг,%") AS max_corg, "layer_name", "Регион", "Свита", "Пласт", "lon", "lat" FROM df WHERE "Cорг,%" IS NOT NULL GROUP BY "Регион", "Свита", "Пласт", "layer_name", "lon", "lat" ORDER BY max_corg DESC LIMIT 1
- SELECT "layer_name", "Регион", "Rо,%", "lon", "lat" FROM df WHERE "Rо,%" > 1.0 AND "Rо,%" IS NOT NULL LIMIT 10
- SELECT * FROM df WHERE "Rо,%" >= 1.0 AND "Rо,%" IS NOT NULL

НЕПРАВИЛЬНО (НЕ ДЕЛАЙ ТАК):
- SELECT "Region", "Swit", "Plast" - ЭТО НЕПРАВИЛЬНО!
- SELECT "Region" - ЭТО НЕПРАВИЛЬНО! Правильно: "Регион"

ВАЖНО: Всегда включай координаты "lon" и "lat" в SELECT, если они доступны в таблице.

Перед отправкой запроса проверь: все имена колонок должны быть на русском языке, кроме lon и lat, и точно совпадать с именами из списка выше!

Сгенерируй SQL запрос, используя ТОЧНЫЕ русские имена колонок из списка выше:"""

    def _load_csv(self):
        """Загрузка CSV файла в DataFrame с обработкой дублирующихся колонок."""
        try:
            self.df = pd.read_csv(self.csv_path)
            
            # Обработка дублирующихся колонок (SQLite не различает регистр)
            # Переименовываем колонки, чтобы избежать конфликтов
            seen_cols = {}
            new_columns = []
            
            for col in self.df.columns:
                col_lower = col.strip().lower()
                if col_lower in seen_cols:
                    # Если колонка уже встречалась, добавляем суффикс
                    count = seen_cols[col_lower]
                    seen_cols[col_lower] = count + 1
                    new_col = f"{col}_dup{count}"
                    new_columns.append(new_col)
                    logger.warning(f"Переименована дублирующаяся колонка '{col}' -> '{new_col}'")
                else:
                    seen_cols[col_lower] = 1
                    new_columns.append(col)
            
            self.df.columns = new_columns
            logger.info(f"Загружен CSV файл: {len(self.df)} строк, {len(self.df.columns)} колонок")
        except Exception as e:
            logger.error(f"Ошибка загрузки CSV: {e}")
            raise

    def _get_columns_info(self) -> str:
        """Получение информации о колонках для промпта."""
        columns_info = []
        for col in self.df.columns:
            dtype = str(self.df[col].dtype)
            non_null_count = self.df[col].notna().sum()
            columns_info.append(f"- `{col}` ({dtype}, заполнено: {non_null_count}/{len(self.df)})")
        return "\n".join(columns_info)

    def formalize_query(self, user_query: str) -> str:
        """
        Формализация запроса пользователя с помощью GigaChat.
        
        Args:
            user_query: Естественный запрос пользователя
            
        Returns:
            Формализованный запрос
        """
        logger.info(f"Формализация запроса: {user_query}")
        
        full_prompt = f"{self.formalization_prompt}\n\nЗапрос пользователя: {user_query}\n\nФормализованный запрос:"
        
        try:
            with GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False
            ) as giga:
                response = giga.chat(full_prompt)
                formalized = response.choices[0].message.content.strip()
                logger.info(f"Формализованный запрос: {formalized}")
                return formalized
        except Exception as e:
            logger.error(f"Ошибка формализации запроса: {e}")
            raise

    def generate_sql(self, formalized_query: str) -> str:
        """
        Генерация SQL запроса на основе формализованного запроса.
        
        Args:
            formalized_query: Формализованный запрос
            
        Returns:
            SQL запрос
        """
        logger.info(f"Генерация SQL для формализованного запроса: {formalized_query}")
        
        columns_info = self._get_columns_info()
        full_prompt = self.sql_generation_prompt_template.format(
            formalized_query=formalized_query,
            columns_info=columns_info
        )
        
        try:
            with GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False
            ) as giga:
                response = giga.chat(full_prompt)
                sql_query = response.choices[0].message.content.strip()
                
                # Очистка SQL запроса от возможных markdown блоков
                if sql_query.startswith("```sql"):
                    sql_query = sql_query[6:]
                if sql_query.startswith("```"):
                    sql_query = sql_query[3:]
                if sql_query.endswith("```"):
                    sql_query = sql_query[:-3]
                sql_query = sql_query.strip()
                
                # Удаление комментариев из SQL запроса
                sql_query = re.sub(r'--.*?$', '', sql_query, flags=re.MULTILINE)
                
                # Очистка от двойных кавычек внутри кавычек (исправление ""Rо,%"" -> "Rо,%")
                sql_query = self._fix_double_quotes(sql_query)
                
                # Исправление алиасов и ORDER BY для колонок с специальными символами
                sql_query = self._fix_aliases_and_order_by(sql_query)
                
                # Проверка и автоматическое добавление координат lon и lat в SELECT
                sql_query = self._ensure_coordinates_in_select(sql_query)
                
                logger.info(f"Сгенерированный SQL (после проверки координат): {sql_query}")
                return sql_query
        except Exception as e:
            logger.error(f"Ошибка генерации SQL: {e}")
            raise

    def _fix_double_quotes(self, sql_query: str) -> str:
        """
        Исправляет двойные кавычки внутри кавычек (""Rо,%"" -> "Rо,%").
        
        Args:
            sql_query: SQL запрос
            
        Returns:
            Исправленный SQL запрос
        """
        original_query = sql_query
        fixed_query = sql_query
        
        # Более агрессивное исправление: заменяем все случаи двойных кавычек подряд
        # Сначала обрабатываем случаи с содержимым между кавычками
        # Паттерн: ""любой_текст"" -> "любой_текст"
        fixed_query = re.sub(r'""([^"]+)""', r'"\1"', fixed_query)
        
        # Также исправляем случаи с тройными кавычками
        fixed_query = re.sub(r'"""([^"]+)"""', r'"\1"', fixed_query)
        
        # Исправляем случаи, когда есть пробелы между кавычками
        fixed_query = re.sub(r'""\s*([^"]+)\s*""', r'"\1"', fixed_query)
        
        # Убираем лишние кавычки в начале и конце идентификаторов
        fixed_query = re.sub(r'""([^"]+)"', r'"\1"', fixed_query)
        fixed_query = re.sub(r'"([^"]+)""', r'"\1"', fixed_query)
        
        # Исправляем все оставшиеся случаи двойных кавычек подряд (включая пустые)
        # Это должно обработать все случаи типа "" -> "
        # Используем цикл для обработки вложенных случаев
        max_iterations = 10
        for _ in range(max_iterations):
            new_query = re.sub(r'""', r'"', fixed_query)
            if new_query == fixed_query:
                break
            fixed_query = new_query
        
        # Финальная проверка: убираем оставшиеся пустые кавычки
        fixed_query = re.sub(r'""', r'"', fixed_query)
        
        if fixed_query != original_query:
            logger.info("Исправлены двойные кавычки в SQL запросе")
            logger.debug(f"Было: {original_query[:200]}...")
            logger.debug(f"Стало: {fixed_query[:200]}...")
        
        return fixed_query

    def _fix_aliases_and_order_by(self, sql_query: str) -> str:
        """
        Исправляет алиасы и ORDER BY для колонок с специальными символами (%, запятые и т.д.).
        Также убирает ненужную конкатенацию с '%' в SELECT.
        
        Args:
            sql_query: SQL запрос
            
        Returns:
            Исправленный SQL запрос
        """
        original_query = sql_query
        fixed_query = sql_query
        
        # Убираем ненужную конкатенацию || '%' в SELECT (значения уже в процентах)
        fixed_query = re.sub(r'"([^"]+)"\s*\|\|\s*[\'"]%[\'"]', r'"\1"', fixed_query)
        
        # Исправляем алиасы типа AS Rо,% на AS "Rо,%" или убираем алиас
        # Паттерн: AS column_name_with_special_chars
        # Ищем колонки с %, запятыми и другими специальными символами в алиасах
        fixed_query = re.sub(
            r'AS\s+([A-Za-zА-Яа-яёЁ0-9_,%]+)',
            lambda m: f'AS "{m.group(1)}"' if any(c in m.group(1) for c in ['%', ',', ' ', '-']) else m.group(0),
            fixed_query,
            flags=re.IGNORECASE
        )
        
        # Исправляем ORDER BY - более надежный подход
        # Сначала находим весь блок ORDER BY
        order_by_pattern = r'(ORDER\s+BY\s+)(.*?)(?:\s+(LIMIT|$))'
        
        def fix_order_by_block(match):
            order_keyword = match.group(1)
            order_clause = match.group(2).strip()
            limit_part = match.group(3) if match.lastindex >= 3 else ''
            
            # Разбиваем на отдельные колонки, учитывая кавычки
            columns = []
            current_col = ''
            in_quotes = False
            quote_char = None
            
            i = 0
            while i < len(order_clause):
                char = order_clause[i]
                
                if char in ['"', "'", '`'] and (i == 0 or order_clause[i-1] != '\\'):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                        current_col += char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                        current_col += char
                    else:
                        current_col += char
                elif char == ',' and not in_quotes:
                    if current_col.strip():
                        columns.append(current_col.strip())
                    current_col = ''
                else:
                    current_col += char
                
                i += 1
            
            if current_col.strip():
                columns.append(current_col.strip())
            
            # Исправляем каждую колонку
            fixed_columns = []
            for col in columns:
                col = col.strip()
                # Если колонка содержит специальные символы и не в кавычках, добавляем кавычки
                if any(c in col for c in ['%', ',', ' ', '-']) and not (col.startswith('"') and col.endswith('"')):
                    # Убираем возможные неправильные кавычки
                    col_clean = re.sub(r'^["`\']+|["`\']+$', '', col)
                    # Убираем лишние пробелы и кавычки внутри
                    col_clean = re.sub(r'\s*["`\']+\s*', '', col_clean)
                    fixed_columns.append(f'"{col_clean}"')
                else:
                    # Проверяем, нет ли разорванных кавычек типа "Rо, "%"
                    if '"' in col and col.count('"') % 2 != 0:
                        # Исправляем разорванные кавычки
                        col_fixed = re.sub(r'["`\']+\s*["`\']+', '"', col)
                        col_fixed = re.sub(r'([^"])\s*["`\']+([^"])', r'\1"\2', col_fixed)
                        fixed_columns.append(col_fixed)
                    else:
                        fixed_columns.append(col)
            
            result = f'{order_keyword}{", ".join(fixed_columns)}'
            if limit_part:
                result += f' {limit_part}'
            return result
        
        fixed_query = re.sub(order_by_pattern, fix_order_by_block, fixed_query, flags=re.IGNORECASE | re.DOTALL)
        
        if fixed_query != original_query:
            logger.info("Исправлены алиасы и ORDER BY в SQL запросе")
            logger.debug(f"Было: {original_query[:200]}...")
            logger.debug(f"Стало: {fixed_query[:200]}...")
        
        return fixed_query

    def _ensure_coordinates_in_select(self, sql_query: str) -> str:
        """
        Проверяет наличие колонок lon и lat в SELECT запросе и добавляет их, если они есть в таблице.
        
        Args:
            sql_query: SQL запрос
            
        Returns:
            SQL запрос с гарантированным наличием lon и lat в SELECT (если они есть в таблице)
        """
        # Проверяем, есть ли колонки lon и lat в таблице
        has_lon = 'lon' in self.df.columns
        has_lat = 'lat' in self.df.columns
        
        if not (has_lon and has_lat):
            logger.debug("Колонки lon и/или lat отсутствуют в таблице, пропускаем проверку")
            return sql_query
        
        logger.info("Проверка наличия координат lon и lat в SQL запросе...")
        
        # Проверяем, есть ли уже lon и lat в SELECT
        # Ищем SELECT ... FROM в запросе (регистронезависимо)
        # Улучшенное регулярное выражение для обработки многострочных запросов
        select_pattern = r'(SELECT\s+)(.*?)(\s+FROM\s+)'
        match = re.search(select_pattern, sql_query, re.IGNORECASE | re.DOTALL)
        
        if not match:
            logger.warning("Не удалось найти SELECT ... FROM в SQL запросе")
            return sql_query
        
        select_keyword = match.group(1)
        select_columns = match.group(2).strip()
        from_keyword = match.group(3)
        
        # Убираем возможные переносы строк и лишние пробелы из списка колонок
        select_columns = re.sub(r'\s+', ' ', select_columns).strip()
        
        # Проверяем, есть ли уже lon и lat в SELECT
        # Ищем точные совпадения с учетом кавычек и алиасов
        has_lon_in_select = bool(re.search(r'["`]?lon["`]?\s*(?:AS\s+\w+)?', select_columns, re.IGNORECASE))
        has_lat_in_select = bool(re.search(r'["`]?lat["`]?\s*(?:AS\s+\w+)?', select_columns, re.IGNORECASE))
        
        logger.info(f"Координаты в SELECT: lon={has_lon_in_select}, lat={has_lat_in_select}")
        
        # Если обе координаты уже есть, возвращаем запрос без изменений
        if has_lon_in_select and has_lat_in_select:
            logger.info("Координаты lon и lat уже присутствуют в SELECT запросе")
            return sql_query
        
        # Если координаты отсутствуют, добавляем их
        columns_to_add = []
        if not has_lon_in_select:
            columns_to_add.append('"lon"')
        if not has_lat_in_select:
            columns_to_add.append('"lat"')
        
        if columns_to_add:
            logger.info(f"Добавляем координаты в SELECT: {columns_to_add}")
            
            # Проверяем, есть ли SELECT * (все колонки)
            if select_columns.strip() == '*':
                # Если SELECT *, заменяем на SELECT *, "lon", "lat"
                new_select = f'{select_keyword}*, {", ".join(columns_to_add)}{from_keyword}'
            else:
                # Добавляем координаты в конец списка колонок
                # Убираем возможную точку с запятой в конце
                select_columns_clean = select_columns.rstrip(';').strip()
                # Убираем запятую в конце, если есть
                select_columns_clean = select_columns_clean.rstrip(',').strip()
                new_select = f'{select_keyword}{select_columns_clean}, {", ".join(columns_to_add)}{from_keyword}'
            
            # Заменяем SELECT часть в запросе
            sql_query = re.sub(select_pattern, new_select, sql_query, flags=re.IGNORECASE | re.DOTALL)
            logger.info(f"SQL запрос обновлен: координаты {columns_to_add} добавлены в SELECT")
            
            # Проверяем наличие GROUP BY и добавляем координаты туда, если нужно
            sql_query = self._ensure_coordinates_in_group_by(sql_query, columns_to_add)
        
        return sql_query
    
    def _ensure_coordinates_in_group_by(self, sql_query: str, coordinates_added: List[str]) -> str:
        """
        Проверяет наличие GROUP BY и добавляет координаты в GROUP BY, если они были добавлены в SELECT.
        
        Args:
            sql_query: SQL запрос
            coordinates_added: Список добавленных координат (например, ['"lon"', '"lat"'])
            
        Returns:
            SQL запрос с координатами в GROUP BY (если есть GROUP BY)
        """
        # Проверяем, есть ли GROUP BY в запросе
        group_by_pattern = r'(GROUP\s+BY\s+)(.*?)(?:\s+(ORDER|HAVING|LIMIT|$))'
        match = re.search(group_by_pattern, sql_query, re.IGNORECASE | re.DOTALL)
        
        if not match:
            logger.debug("GROUP BY отсутствует в запросе, координаты не нужно добавлять в GROUP BY")
            return sql_query
        
        logger.info("Обнаружен GROUP BY, проверяем наличие координат...")
        
        group_by_keyword = match.group(1)
        group_by_columns = match.group(2).strip()
        after_group_by = match.group(3) if match.lastindex >= 3 else ''
        
        # Убираем возможные переносы строк и лишние пробелы
        group_by_columns = re.sub(r'\s+', ' ', group_by_columns).strip()
        
        # Проверяем, есть ли уже координаты в GROUP BY
        has_lon_in_group_by = bool(re.search(r'["`]?lon["`]?\s*(?:,|$)', group_by_columns, re.IGNORECASE))
        has_lat_in_group_by = bool(re.search(r'["`]?lat["`]?\s*(?:,|$)', group_by_columns, re.IGNORECASE))
        
        logger.info(f"Координаты в GROUP BY: lon={has_lon_in_group_by}, lat={has_lat_in_group_by}")
        
        # Определяем, какие координаты нужно добавить в GROUP BY
        columns_to_add_to_group_by = []
        if '"lon"' in coordinates_added and not has_lon_in_group_by:
            columns_to_add_to_group_by.append('"lon"')
        if '"lat"' in coordinates_added and not has_lat_in_group_by:
            columns_to_add_to_group_by.append('"lat"')
        
        if columns_to_add_to_group_by:
            logger.info(f"Добавляем координаты в GROUP BY: {columns_to_add_to_group_by}")
            
            # Убираем возможную запятую в конце
            group_by_columns_clean = group_by_columns.rstrip(',').strip()
            
            # Формируем новый GROUP BY
            if after_group_by:
                new_group_by = f'{group_by_keyword}{group_by_columns_clean}, {", ".join(columns_to_add_to_group_by)} {after_group_by}'
            else:
                new_group_by = f'{group_by_keyword}{group_by_columns_clean}, {", ".join(columns_to_add_to_group_by)}'
            
            # Заменяем GROUP BY часть в запросе
            sql_query = re.sub(group_by_pattern, new_group_by, sql_query, flags=re.IGNORECASE | re.DOTALL)
            logger.info(f"SQL запрос обновлен: координаты {columns_to_add_to_group_by} добавлены в GROUP BY")
        
        return sql_query

    def _normalize_sql(self, sql_query: str) -> str:
        """
        Нормализация SQL запроса для pandasql.
        
        Args:
            sql_query: Исходный SQL запрос
            
        Returns:
            Нормализованный SQL запрос
        """
        # Убираем лишние пробелы и переносы строк, но сохраняем структуру
        # Заменяем множественные пробелы/переносы строк на один пробел
        # Но сохраняем пробелы внутри обратных кавычек
        sql_query = sql_query.strip()
        
        # Заменяем множественные пробелы и переносы строк на один пробел
        # Но не трогаем содержимое внутри обратных кавычек
        # Простая нормализация - заменяем только множественные пробелы/табы/переносы на один пробел
        sql_query = re.sub(r'[ \t\n\r]+', ' ', sql_query)
        sql_query = sql_query.strip()
        
        return sql_query

    def execute_query(self, sql_query: str) -> pd.DataFrame:
        """
        Выполнение SQL запроса к CSV файлу.
        
        Args:
            sql_query: SQL запрос
            
        Returns:
            DataFrame с результатами
        """
        logger.info(f"Выполнение SQL запроса: {sql_query}")
        
        try:
            # Нормализация SQL запроса
            sql_query = self._normalize_sql(sql_query)
            logger.debug(f"Нормализованный SQL: {sql_query}")
            
            # Валидация имен колонок в SQL запросе
            # Извлекаем имена колонок из SQL запроса (между обратными или двойными кавычками)
            # DuckDB использует двойные кавычки, pandasql - обратные
            quoted_cols_backtick = re.findall(r'`([^`]+)`', sql_query)
            quoted_cols_double = re.findall(r'"([^"]+)"', sql_query)
            quoted_cols = quoted_cols_backtick + quoted_cols_double
            
            # Проверяем, что все упомянутые колонки существуют
            # И создаем маппинг для автоматического исправления распространенных ошибок
            column_mapping = {
                'Region': 'Регион',
                'Swit': 'Свита',
                'Plast': 'Пласт',
                'region': 'Регион',
                'swit': 'Свита',
                'plast': 'Пласт',
                'REGION': 'Регион',
                'SWIT': 'Свита',
                'PLAST': 'Пласт',
            }
            
            # Исправляем имена колонок в SQL запросе
            sql_query_fixed = sql_query
            missing_cols = []
            fixed_cols = {}
            
            extended_column_mapping = {
                **column_mapping,
                'R0': 'Rо,%',
                'r0': 'Rо,%',
                'R0%': 'Rо,%',
                'R0,%': 'Rо,%',
                'Сорг': 'Сорг,%',
                'сорг': 'Сорг,%',
                'Cорг': 'Сорг,%',
                'Сорг%': 'Сорг,%',
                'Сорг,%': 'Сорг,%',
                'Cорг,%': 'Сорг,%',
            }
            
            for col in quoted_cols:
                if col not in self.df.columns:
                    missing_cols.append(col)
                    # Пробуем найти исправление
                    if col in extended_column_mapping:
                        correct_name = extended_column_mapping[col]
                        if correct_name in self.df.columns:
                            # Заменяем в SQL запросе (учитываем разные форматы кавычек)
                            sql_query_fixed = sql_query_fixed.replace(f'"{col}"', f'"{correct_name}"')
                            sql_query_fixed = sql_query_fixed.replace(f'`{col}`', f'"{correct_name}"')
                            sql_query_fixed = sql_query_fixed.replace(f'{col}', f'"{correct_name}"')
                            fixed_cols[col] = correct_name
                            logger.info(f"Автоматически исправлено имя колонки: '{col}' -> '{correct_name}'")
                    else:
                        # Пробуем найти похожую колонку по смыслу
                        possible_matches = []
                        col_lower = col.lower()
                        for df_col in self.df.columns:
                            df_col_lower = df_col.lower()
                            # Проверяем различные варианты совпадений
                            if col_lower in df_col_lower or df_col_lower in col_lower:
                                possible_matches.append(df_col)
                            # Проверяем транслитерацию
                            if col == 'Region' and 'Регион' in df_col:
                                possible_matches.append(df_col)
                            elif col == 'Swit' and 'Свита' in df_col:
                                possible_matches.append(df_col)
                            elif col == 'Plast' and 'Пласт' in df_col:
                                possible_matches.append(df_col)
                        
                        if possible_matches:
                            best_match = possible_matches[0]
                            sql_query_fixed = sql_query_fixed.replace(f'"{col}"', f'"{best_match}"')
                            sql_query_fixed = sql_query_fixed.replace(f'`{col}`', f'"{best_match}"')
                            fixed_cols[col] = best_match
                            logger.info(f"Автоматически исправлено имя колонки: '{col}' -> '{best_match}'")
            
            # Дополнительная проверка: исправляем R0 в WHERE условиях, если используется неправильное имя
            # Ищем паттерны типа "R0" или "R0%" в WHERE условиях
            r0_patterns = [
                (r'\bR0\b', 'Rо,%'),
                (r'"R0"', 'Rо,%'),
                (r'`R0`', 'Rо,%'),
                (r'\bR0%\b', 'Rо,%'),
                (r'"R0%"', 'Rо,%'),
            ]
            
            for pattern, replacement in r0_patterns:
                if re.search(pattern, sql_query_fixed, re.IGNORECASE):
                    sql_query_fixed = re.sub(pattern, replacement, sql_query_fixed, flags=re.IGNORECASE)
                    if 'R0' not in fixed_cols:
                        fixed_cols['R0'] = 'Rо,%'
                        logger.info(f"Автоматически исправлено R0 в WHERE условии на 'Rо,%'")
            
            # Если были исправления, используем исправленный запрос
            if fixed_cols:
                sql_query = sql_query_fixed
                logger.info(f"SQL запрос исправлен. Исправленные колонки: {fixed_cols}")
            
            # Проверяем оставшиеся отсутствующие колонки
            remaining_missing = [col for col in missing_cols if col not in fixed_cols]
            if remaining_missing:
                available_cols = [c for c in self.df.columns if any(mc.lower() in c.lower() for mc in remaining_missing)]
                error_msg = f"Колонки не найдены и не могут быть исправлены: {remaining_missing}\n"
                if available_cols:
                    error_msg += f"Возможно имелись в виду: {available_cols[:10]}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Убеждаемся, что sql_query - это строка
            if not isinstance(sql_query, str):
                sql_query = str(sql_query)
            
            # Используем DuckDB (предпочтительно) или pandasql (запасной вариант)
            if USE_DUCKDB:
                # DuckDB - более надежный и быстрый вариант
                conn = duckdb.connect()
                # Регистрируем DataFrame как таблицу
                conn.register('df', self.df)
                # Выполняем SQL запрос
                result = conn.execute(sql_query).df()
               
                conn.close()
            else:
                # Используем pandasql как запасной вариант
                df = self.df  # Локальная переменная для pandasql
                # Пробуем разные способы вызова sqldf
                try:
                    # Способ 1: через locals()
                    result = sqldf(sql_query, locals())
                except (TypeError, AttributeError) as e1:
                    error_str = str(e1).lower()
                    if "executable" in error_str or "callable" in error_str:
                        # Способ 2: через явный словарь
                        local_vars = {'df': df}
                        result = sqldf(sql_query, local_vars)
                    else:
                        raise e1
            
            logger.info(f"Запрос выполнен успешно. Найдено строк: {len(result)}")
            logger.info(f"Результат запроса: {result}")
            return result
        except Exception as e:
            logger.error(f"Ошибка выполнения SQL запроса: {e}")
            logger.error(f"SQL запрос: {sql_query}")
            logger.error(f"Тип SQL запроса: {type(sql_query)}")
            logger.error(f"Длина SQL запроса: {len(sql_query)}")
            # Выводим список доступных колонок для отладки
            logger.info(f"Доступные колонки (первые 20): {list(self.df.columns[:20])}")
            raise

    def format_response(self, user_query: str, result_df: pd.DataFrame) -> str:
        """
        Форматирование ответа через GigaChat для красивого вывода.
        
        Args:
            user_query: Исходный запрос пользователя
            result_df: DataFrame с результатами запроса
            
        Returns:
            Красиво отформатированный ответ
        """
        # Подготовка данных для промпта
        if len(result_df) == 0:
            data_summary = "Результаты не найдены."
            coords_section = ""
        else:
            # Преобразуем DataFrame в читаемый формат
            data_summary = result_df.to_string(index=False)
            
            # Подготовка информации о координатах отдельно и явно
            coords_section = ""
            coords_list = []
            
            # Проверяем наличие колонок с координатами
            has_lon = 'lon' in result_df.columns
            has_lat = 'lat' in result_df.columns
            
            logger.info(f"Проверка координат: lon колонка есть={has_lon}, lat колонка есть={has_lat}")
            
            if has_lon and has_lat:
                for idx, row in result_df.iterrows():
                    lon = row.get('lon', None)
                    lat = row.get('lat', None)
                    
                    logger.debug(f"Строка {idx}: lon={lon} (тип: {type(lon)}), lat={lat} (тип: {type(lat)})")
                    
                    # Обрабатываем координаты, которые могут быть в разных форматах
                    lon_str = None
                    lat_str = None
                    
                    # Проверяем, что значения не пустые
                    if lon is not None and str(lon).strip() not in ['', 'nan', 'None', 'null', 'NULL']:
                        lon_str = str(lon).strip()
                        # Обрабатываем массивы в формате "[44.317724338683696, 48.09110311146138]"
                        if lon_str.startswith('[') and lon_str.endswith(']'):
                            # Извлекаем первое значение из массива
                            try:
                                import ast
                                lon_array = ast.literal_eval(lon_str)
                                if isinstance(lon_array, list) and len(lon_array) > 0:
                                    lon_str = str(lon_array[0])
                            except:
                                # Если не удалось распарсить, просто убираем скобки
                                lon_str = lon_str.strip('[]').split(',')[0].strip()
                        else:
                            lon_str = lon_str.strip('[]')
                    
                    if lat is not None and str(lat).strip() not in ['', 'nan', 'None', 'null', 'NULL']:
                        lat_str = str(lat).strip()
                        # Обрабатываем массивы в формате "[44.317724338683696, 48.09110311146138]"
                        if lat_str.startswith('[') and lat_str.endswith(']'):
                            # Извлекаем второе значение из массива или первое, если это отдельный массив
                            try:
                                import ast
                                lat_array = ast.literal_eval(lat_str)
                                if isinstance(lat_array, list) and len(lat_array) > 0:
                                    lat_str = str(lat_array[-1]) if len(lat_array) > 1 else str(lat_array[0])
                            except:
                                # Если не удалось распарсить, просто убираем скобки
                                lat_str = lat_str.strip('[]').split(',')[-1].strip()
                        else:
                            lat_str = lat_str.strip('[]')
                    
                    # Если обе координаты найдены, добавляем их
                    if lon_str and lat_str:
                        coords_list.append(f"Место {idx + 1}: Долгота: {lon_str}, Широта: {lat_str}")
                        logger.info(f"Найдены координаты для строки {idx}: lon={lon_str}, lat={lat_str}")
                    else:
                        logger.warning(f"Координаты для строки {idx} неполные: lon={lon_str}, lat={lat_str}")
                
                if coords_list:
                    coords_section = "\n\n" + "="*60 + "\nКООРДИНАТЫ НАЙДЕННЫХ МЕСТ (ОБЯЗАТЕЛЬНО ВКЛЮЧИТЬ В ОТВЕТ):\n" + "="*60 + "\n" + "\n".join(coords_list) + "\n" + "="*60
                    logger.info(f"Подготовлен раздел с координатами: {len(coords_list)} мест")
                else:
                    coords_section = "\n\n" + "="*60 + "\nВНИМАНИЕ: Координаты присутствуют в данных, но не заполнены или имеют неверный формат\n" + "="*60
                    logger.warning("Координаты не были извлечены из данных")
            else:
                coords_section = "\n\n" + "="*60 + "\nВНИМАНИЕ: Координаты отсутствуют в результатах запроса (колонки lon/lat не найдены)\n" + "="*60
                logger.warning(f"Колонки координат отсутствуют: lon={has_lon}, lat={has_lat}")
            
            # Также добавляем координаты прямо в data_summary для большей видимости
            if coords_list:
                data_summary += "\n\n" + "ВАЖНО: Координаты присутствуют в данных выше!"
        
        # Определяем, есть ли данные
        has_data = len(result_df) > 0 and data_summary != "Результаты не найдены."
        
        
        if not has_data:
            # Промпт для случая отсутствия данных
            formatting_prompt = f"""Ты - помощник для анализа геологических данных Каспийского моря.

Пользователь задал вопрос: "{user_query}"

Результаты запроса к базе данных:
{data_summary}

СТРОГИЕ ТРЕБОВАНИЯ К ОТВЕТУ:

1. ОБЯЗАТЕЛЬНО сообщи пользователю, что по его запросу данные в базе не найдены
2. Объясни возможные причины отсутствия данных:
   - Заданные параметры поиска слишком строгие
   - Данные по указанным критериям отсутствуют в базе
   - Возможно, стоит уточнить параметры поиска
3. Предложи альтернативные варианты:
   - Расширить критерии поиска
   - Уточнить регион или другие параметры
   - Использовать более общий запрос

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
К сожалению, по вашему запросу "{user_query}" данные в базе не найдены.

Возможные причины:
- Заданные параметры поиска слишком строгие
- Данные по указанным критериям отсутствуют в базе
- Возможно, стоит уточнить параметры поиска

Попробуйте:
- Расширить критерии поиска
- Уточнить регион или другие параметры
- Использовать более общий запрос

Верни ТОЛЬКО отформатированный ответ без дополнительных комментариев."""
        else:
            # Промпт для случая наличия данных
            # Делаем координаты еще более заметными в промпте
            coords_highlight = ""
            if coords_section and "КООРДИНАТЫ НАЙДЕННЫХ МЕСТ" in coords_section:
                coords_highlight = "\n\n" + "!"*60 + "\nВНИМАНИЕ! ВНИМАНИЕ! ВНИМАНИЕ!\n" + "!"*60 + "\nВ ДАННЫХ НИЖЕ ЕСТЬ РАЗДЕЛ С КООРДИНАТАМИ!\nТЫ ОБЯЗАН ВКЛЮЧИТЬ ИХ В СВОЙ ОТВЕТ!\nНЕ ПРОПУСКАЙ КООРДИНАТЫ!\n" + "!"*60 + "\n"
            
            formatting_prompt = f"""Ты - помощник для анализа геологических данных Каспийского моря.

Пользователь задал вопрос: "{user_query}"

Результаты запроса к базе данных:
{data_summary}{coords_section}{coords_highlight}

СТРОГИЕ ТРЕБОВАНИЯ К ФОРМАТУ ОТВЕТА (НЕ НАРУШАЙ ИХ!):

1. ОБЯЗАТЕЛЬНО начни ответ с прямого ответа на вопрос пользователя (1-2 предложения)

2. КРИТИЧЕСКИ ВАЖНО - ОБЯЗАТЕЛЬНО включи раздел с координатами:
   - Если выше есть раздел "КООРДИНАТЫ НАЙДЕННЫХ МЕСТ" с координатами, ТЫ ОБЯЗАН включить их в ответ
   - Формат: "📍 КООРДИНАТЫ: Долгота: [точное значение], Широта: [точное значение]"
   - Если координат несколько мест, перечисли ВСЕ через запятую или списком
   - НЕ ПРОПУСКАЙ координаты ни при каких обстоятельствах!
   - Скопируй координаты ТОЧНО из раздела "КООРДИНАТЫ НАЙДЕННЫХ МЕСТ" выше
   - Если в таблице выше есть колонки "lon" и "lat" с данными, используй их значения

3. Выдели ключевую информацию:
   - Максимальные/минимальные значения (если есть)
   - Географическое местоположение (регион, свита, пласт и т.д.)
   - Важные числовые показатели (Cорг, глубина, температура и т.д.)

4. Используй структурированный формат:
   - Заголовки для разделов
   - Маркированные списки для перечисления
   - Выделение важных чисел жирным текстом (используй **текст** для markdown)

5. Будь конкретным и информативным - не используй общие фразы

6. ПРОВЕРЬ перед отправкой: если в данных выше есть раздел "КООРДИНАТЫ НАЙДЕННЫХ МЕСТ" или колонки lon/lat с данными, то координаты ДОЛЖНЫ быть в твоем ответе!


ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
Максимальное содержание органического углерода (Cорг) в Каспийском море составляет **X%** и находится в регионе [Регион], свита [Свита], пласт [Пласт].

📍 КООРДИНАТЫ: Долгота: [точное значение из данных], Широта: [точное значение из данных]

Дополнительная информация:
- [другие важные данные]

ВНИМАНИЕ: Если ты не включишь координаты в ответ, когда они присутствуют в данных выше, ответ будет считаться неполным и неправильным!

Верни ТОЛЬКО отформатированный ответ без дополнительных комментариев и объяснений."""

        try:
            with GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False
            ) as giga:
                response = giga.chat(formatting_prompt)
                formatted_response = response.choices[0].message.content.strip()
                
                # Проверка: если координаты были в данных, но не включены в ответ, добавляем их принудительно
                if coords_section and "КООРДИНАТЫ НАЙДЕННЫХ МЕСТ" in coords_section and "ОБЯЗАТЕЛЬНО ВКЛЮЧИТЬ" in coords_section:
                    # Проверяем, есть ли координаты в ответе (более строгая проверка)
                    coords_in_response = any(keyword in formatted_response.lower() for keyword in [
                        'координат', 'долгот', 'широт', '📍', 'долгота', 'широта', 'lon', 'lat'
                    ])
                    
                    if not coords_in_response:
                        logger.warning("Координаты не были включены в ответ GigaChat, добавляем их принудительно")
                        # Извлекаем координаты из coords_section
                        coords_lines = [line for line in coords_section.split('\n') if 'Долгота:' in line and 'Широта:' in line]
                        if coords_lines:
                            coords_text = "\n\n📍 КООРДИНАТЫ:\n" + "\n".join([line.replace("Место ", "• ") for line in coords_lines])
                            formatted_response += coords_text
                            logger.info(f"Координаты добавлены принудительно: {len(coords_lines)} мест")
                    else:
                        logger.info("Координаты найдены в ответе GigaChat")
                
                # Дополнительная проверка: если координаты есть в таблице, но не были извлечены
                if not coords_list and has_data and 'lon' in result_df.columns and 'lat' in result_df.columns:
                    logger.warning("Попытка извлечь координаты напрямую из таблицы...")
                    # Пробуем извлечь координаты напрямую из таблицы
                    table_coords = []
                    for idx, row in result_df.iterrows():
                        lon_val = row.get('lon', None)
                        lat_val = row.get('lat', None)
                        if lon_val is not None and lat_val is not None:
                            lon_str = str(lon_val).strip()
                            lat_str = str(lat_val).strip()
                            if lon_str not in ['', 'nan', 'None', 'null', 'NULL'] and lat_str not in ['', 'nan', 'None', 'null', 'NULL']:
                                table_coords.append(f"• Долгота: {lon_str}, Широта: {lat_str}")
                    
                    if table_coords:
                        logger.info(f"Найдены координаты в таблице: {len(table_coords)} мест")
                        coords_text = "\n\n📍 КООРДИНАТЫ (из таблицы):\n" + "\n".join(table_coords)
                        # Проверяем, не добавлены ли уже координаты
                        if '📍' not in formatted_response:
                            formatted_response += coords_text
                
                return formatted_response
        except Exception as e:
            logger.error(f"Ошибка форматирования ответа: {e}")
            # Возвращаем базовый формат с координатами, если форматирование не удалось
            fallback_response = f"Результаты запроса:\n\n{data_summary}"
            if coords_section and "КООРДИНАТЫ НАЙДЕННЫХ МЕСТ" in coords_section:
                fallback_response += coords_section
            return fallback_response

    def query(self, user_query: str, format_output: bool = True) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Полный цикл: формализация запроса, генерация SQL и выполнение.
        
        Args:
            user_query: Естественный запрос пользователя
            format_output: Форматировать ли ответ через GigaChat
            
        Returns:
            Tuple[DataFrame с результатами, Отформатированный ответ (если format_output=True)]
        """
        # Этап 1: Формализация запроса
        formalized_query = self.formalize_query(user_query)
        
        # Этап 2: Генерация SQL
        sql_query = self.generate_sql(formalized_query)
        
        # Этап 3: Выполнение SQL запроса
        result = self.execute_query(sql_query)
        
        # Этап 4: Форматирование ответа (опционально)
        formatted_response = None
        if format_output:
            formatted_response = self.format_response(user_query, result)
        
        return result, formatted_response


if __name__ == "__main__":
    # Инициализация для HTTPS
    '''manager = OpenSearchManager(
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
        logger.warning(f"Файл {csv_path} не найден. Проверьте путь к файлу.")'''

    # Пример использования CSVSQLEngine для SQL запросов к CSV
    csv_path = "/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/parsed_layers.csv"
    
    if os.path.exists(csv_path):
        logger.info("Инициализация CSVSQLEngine...")
        sql_engine = CSVSQLEngine(
            csv_path=csv_path,
            credentials=GIGACHAT_CREDENTIALS
        )
        
        # Пример запроса пользователя
        user_query = "Где R0 > 1.0% (зрелая нефть)?"
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Запрос пользователя: {user_query}")
        logger.info(f"{'='*80}\n")
        
        try:
            result, formatted_response = sql_engine.query(user_query, format_output=True)
            
            # Вывод красиво отформатированного ответа
            if formatted_response:
                print("\n" + "="*80)
                print("ОТВЕТ:")
                print("="*80)
                print(formatted_response)
                print("="*80 + "\n")
            
            # Дополнительно выводим таблицу с данными
            if len(result) > 0:
                logger.info(f"\n{'='*80}")
                logger.info(f"Детальные результаты запроса ({len(result)} строк):")
                logger.info(f"{'='*80}")
                print("\n", result.to_string())
                
                # Выводим координаты отдельно, если они есть
                if 'lon' in result.columns and 'lat' in result.columns:
                    print("\n" + "-"*80)
                    print("КООРДИНАТЫ НАЙДЕННЫХ МЕСТ:")
                    print("-"*80)
                    for idx, row in result.iterrows():
                        lon = row.get('lon', 'N/A')
                        lat = row.get('lat', 'N/A')
                        if pd.notna(lon) and pd.notna(lat):
                            print(f"  Место {idx + 1}: Долгота: {lon}, Широта: {lat}")
                        else:
                            print(f"  Место {idx + 1}: Координаты не указаны")
                    print("-"*80 + "\n")
                
                print(f"\nВсего найдено: {len(result)} строк")
            else:
                print("\nРезультаты не найдены.")
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении запроса: {e}")
    else:
        logger.warning(f"CSV файл {csv_path} не найден.")