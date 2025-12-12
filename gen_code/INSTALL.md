# Инструкция по установке зависимостей

## Быстрая установка

```bash
# Активируйте ваше окружение
conda activate rag_env

# Установите основные зависимости
pip install -r requirements.txt
```

## Установка по частям

### 1. Основные зависимости для OpenSearch

```bash
pip install opensearch-py sentence-transformers pandas numpy shapely
```

### 2. LangChain (для RAG функций)

```bash
pip install langchain langchain-openai langchain-community
```

### 3. QGIS (для работы с GIS данными)

**macOS:**
```bash
conda install -c conda-forge qgis pyqgis
```

**Linux:**
```bash
# Через систему пакетов или conda
conda install -c conda-forge qgis pyqgis
```

**Windows:**
```bash
# Используйте OSGeo4W или conda
conda install -c conda-forge qgis pyqgis
```

## Проверка установки

```python
# Проверка основных модулей
python -c "from opensearch_manager import OpenSearchManager; print('✓ OpenSearch OK')"
python -c "from rag_opensearch_integration import CaspianRAGSystem; print('✓ RAG OK')"
```

## Решение проблем

### Ошибка: `ModuleNotFoundError: No module named 'langchain.chains'`

**Решение:** Обновлен код для работы без этого модуля. Установите актуальные версии:
```bash
pip install --upgrade langchain langchain-community
```

### Ошибка: `ModuleNotFoundError: No module named 'langchain_community'`

**Решение:**
```bash
pip install langchain-community
```

### Ошибка: `ModuleNotFoundError: No module named 'opensearchpy'`

**Решение:**
```bash
pip install opensearch-py
```

### Ошибка: QGIS не найден

**Решение:** QGIS устанавливается отдельно через conda или систему пакетов. Если не нужен, можно закомментировать импорты QGIS в коде.

## Минимальная установка (без LLM)

Если не нужны функции генерации ответов через LLM, можно установить только:

```bash
pip install opensearch-py sentence-transformers pandas numpy shapely
```

Система будет работать в режиме поиска без генерации ответов.

