# -*- coding: utf-8 -*-
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

print("Загрузка базы знаний... (подождите немного)")

# 1. Подключаем нашу векторную базу
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
vectorstore = Chroma(persist_directory="C:/Users/pgkm-yurist/chroma_db_genealogy", embedding_function=embeddings)

# 2. Подключаем локальную модель DeepSeek
llm = ChatOllama(model="deepseek-r1:8b", temperature=0)

# 3. Шаблон запроса
prompt = ChatPromptTemplate.from_messages([
    ("system", "Ты — помощник по генеалогии. Отвечай на вопрос пользователя, используя ТОЛЬКО предоставленный контекст. Если в контексте нет ответа, скажи 'В данных нет этой информации'. Не выдумывай факты."),
    ("human", "Контекст:\n{context}\n\nВопрос: {question}")
])

print("--- База знаний загружена. Задайте вопрос (или напишите 'выход' для завершения) ---")

while True:
    question = input("\nВаш вопрос: ")
    if question.lower() == 'выход':
        break
    
    print("Ищу в дереве и думаю над ответом...")
    
    # Ищем 3 самых релевантных куска текста
    docs = vectorstore.similarity_search(question, k=3)
    context_text = "\n\n".join([d.page_content for d in docs])
    
    # Отправляем в DeepSeek
    chain = prompt | llm
    response = chain.invoke({"context": context_text, "question": question})
    
    print(f"\nОтвет: {response.content}")

print("До свидания!")