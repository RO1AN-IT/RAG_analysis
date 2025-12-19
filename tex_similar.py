'''
Скрипт для сравнения схожести текстовых данных.
'''

from fuzzywuzzy import fuzz
from sentence_transformers import SentenceTransformer, util
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model_name = "ai-forever/sbert_large_nlu_ru"
logger.info(f"Загрузка модели эмбеддингов: {model_name}")
embedding_model = SentenceTransformer(model_name)

sentences = ["сорг", "Сорг,%", "R0", "ro", "Ro,%"]

embeddings = embedding_model.encode(sentences, convert_to_tensor=True)
cosine_scores = util.cos_sim(embeddings, embeddings)

print(f"Сходство: {cosine_scores}")


word1 = "сорг"
word2 = "Сорг,%"
word3 = "R0"
word4 = "ro"
word5 = "Ro,%"


similarity12 = fuzz.ratio(word1, word2)
similarity35 = fuzz.ratio(word3, word5)
similarity45 = fuzz.ratio(word4, word5)
similarity15 = fuzz.ratio(word1, word5)

partial_similarity12 = fuzz.partial_ratio(word1, word2)
partial_similarity35 = fuzz.partial_ratio(word3, word5)
partial_similarity45 = fuzz.partial_ratio(word4, word5)
partial_similarity15 = fuzz.partial_ratio(word1, word5)

print(f"Схожесть 1 и 2 {similarity12}")
print(f"Схожесть 3 и 5 {similarity35}")
print(f"Схожесть 4 и 5 {similarity45}")
print(f"Схожесть 1 и 5 {similarity15}")

print(f"Схожесть част 1 и 2 {partial_similarity12}")
print(f"Схожесть част 3 и 5 {partial_similarity35}")
print(f"Схожесть част 4 и 5 {partial_similarity45}")
print(f"Схожесть част 1 и 5 {partial_similarity15}")
print(f"Схожесть част 2 и 5 {fuzz.partial_ratio(word2, word5)}")