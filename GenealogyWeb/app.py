import streamlit as st
import requests
import urllib3
import os
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Генеалогический помощник", page_icon="🌳")
st.title("🌳 Чат с вашим древом")
st.caption("Задайте вопрос. Я найду ответ в ваших файлах GEDCOM.")

BASE_DIR = os.path.dirname(__file__)

@st.cache_resource
def load_vectorstore():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    chroma_path = os.path.join(BASE_DIR, "chroma_db_v2")
    txt_path = os.path.join(BASE_DIR, "my_family_knowledge.txt")
    
    vectorstore = Chroma(persist_directory=chroma_path, embedding_function=embeddings)
    
    if vectorstore._collection.count() == 0:
        st.info("Пересоздаем базу знаний...")
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()
            raw_people = content.split("---")
            docs = [Document(page_content=p.strip()) for p in raw_people if p.strip()]
            vectorstore = Chroma.from_documents(documents=docs, embedding=embeddings, persist_directory=chroma_path)
        else:
            st.error("Файл базы знаний не найден.")
            
    return vectorstore

try:
    vectorstore = load_vectorstore()
    count = vectorstore._collection.count()
    if count > 0:
        st.success(f"База знаний загружена! Найдено человек: {count}")
    else:
        st.stop()
except Exception as e:
    st.error(f"Ошибка загрузки базы: {e}")
    st.stop()

with st.form("my_form"):
    question = st.text_input("Ваш вопрос:", placeholder="Например: Кто такой Андрей Спицин?")
    submitted = st.form_submit_button("Спросить")

if submitted and question:
    with st.spinner("Ищу в дереве и думаю над ответом..."):
        try:
            # --- УМНЫЙ ПОИСК ---
            # 1. Извлекаем все документы из базы
            all_docs = vectorstore.get()['documents']
            
            # 2. Ищем точные совпадения по словам из вопроса (длиной больше 3 символов)
            # Это поможет найти "Спицин", "Андрей", "Мавра" и т.д.
            words_to_find = [word.lower().strip("?.,!") for word in question.split() if len(word) > 3]
            
            exact_matches = []
            for doc in all_docs:
                doc_lower = doc.lower()
                if any(word in doc_lower for word in words_to_find):
                    exact_matches.append(doc)
            
            # Если нашли точные совпадения, берем первые 3
            if exact_matches:
                final_docs = exact_matches[:3]
                search_type = "Точный поиск по словам"
            else:
                # Если не нашли, используем векторный поиск (по смыслу)
                docs = vectorstore.similarity_search(question, k=3)
                final_docs = [d.page_content for d in docs]
                search_type = "Поиск по смыслу (векторный)"

            context_text = "\n\n".join(final_docs)

            with st.expander(f"🛠️ Что нашла база ({search_type})"):
                st.write(context_text)

            folder_id = st.secrets["YANDEX_FOLDER_ID"]
            api_key = st.secrets["YANDEX_API_KEY"]
            
            url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
            headers = {
                "Authorization": f"Api-Key {api_key}",
                "Content-Type": "application/json"
            }

            prompt = f"""Ты — помощник по генеалогии. Отвечай на вопрос пользователя, используя ТОЛЬКО предоставленный контекст. Если в контексте нет ответа, скажи 'В данных нет этой информации'.
            
Контекст:
{context_text}

Вопрос: {question}
Ответ:"""

            payload = {
                "modelUri": f"gpt://{folder_id}/yandexgpt-lite/latest",
                "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": 1000},
                "messages": [{"role": "user", "text": prompt}]
            }

            response = requests.post(url, headers=headers, json=payload, verify=False, timeout=30)
            response.raise_for_status()
            
            answer = response.json()['result']['alternatives'][0]['message']['text']
            st.markdown("### Ответ:")
            st.write(answer)

        except Exception as e:
            st.error(f"Произошла ошибка: {e}")
