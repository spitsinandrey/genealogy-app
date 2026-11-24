# -*- coding: utf-8 -*-
import requests
import json
import urllib3
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# Отключаем предупреждения о небезопасном SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("Загрузка базы знаний... (подождите немного)")

# 1. Подключаем нашу векторную базу
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
vectorstore = Chroma(persist_directory="C:/Users/pgkm-yurist/chroma_db_genealogy", embedding_function=embeddings)

# 2. Настройки YandexGPT
folder_id = "b1gftvupbuhf9ss6jia2"  # Ваш Folder ID
api_key = "AQVNzCVq9C-n8itOFh6aJrcC_C_7a2Rfptwaubrc"      # <-- ВСТАВЬТЕ ВАШ КЛЮЧ

url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
headers = {
    "Authorization": f"Api-Key {api_key}",
    "x-folder-id": folder_id,
    "Content-Type": "application/json"
}

print("--- База знаний загружена. Задайте вопрос (или напишите 'выход' для завершения) ---")

while True:
    question = input("\nВаш вопрос: ")
    if question.lower() == 'выход':
        break
    
    print("Ищу в дереве и думаю над ответом...")
    
    # Ищем 3 самых релевантных куска текста
    docs = vectorstore.similarity_search(question, k=3)
    context_text = "\n\n".join([d.page_content for d in docs])
    
    prompt = f"""Ты — помощник по генеалогии. Отвечай на вопрос пользователя, используя ТОЛЬКО предоставленный контекст. Если в контексте нет ответа, скажи 'В данных нет этой информации'.
    
Контекст:
{context_text}

Вопрос: {question}
Ответ:"""

    payload = {
        "modelUri": f"gpt://{folder_id}/yandexgpt",
        "completionOptions": {
            "stream": False,
            "temperature": 0.1,
            "maxTokens": 1000
        },
        "messages": [
            {
                "role": "user",
                "text": prompt
            }
        ]
    }

    try:
        # Используем requests с verify=False для обхода проблем SSL на старой Windows
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=30)
        response.raise_for_status() # Проверка на HTTP ошибки
        
        response_data = response.json()
        answer = response_data['result']['alternatives'][0]['message']['text']
        print(f"\nОтвет: {answer}")
        
    except requests.exceptions.HTTPError as e:
        print(f"\nОшибка API (HTTP {e.response.status_code}): {e.response.text}")
    except Exception as e:
        print(f"\nСистемная ошибка: {e}")

print("До свидания!")
