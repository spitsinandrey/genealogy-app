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
    
    # Если база пустая, пересобираем её
    if vectorstore._collection.count() == 0:
        st.info("Пересоздаем базу знаний (разделяем людей по одному)...")
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Разделяем файл по маркеру --- (один человек = один документ)
            raw_people = content.split("---")
            
            # Очищаем пустые куски и создаем документы LangChain
            docs = [Document(page_content=p.strip()) for p in raw_people if p.strip()]
            
            vectorstore = Chroma.from_documents(documents=docs, embedding=embeddings, persist_directory=chroma_path)
        else:
            st.error(f"Файл не найден по пути: {txt_path}")
            
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
            # Теперь ищем 3 самых близких человека
            docs = vectorstore.similarity_search(question, k=3)
            context_text = "\n\n".join([d.page_content for d in docs])

            with st.expander("🛠️ Посмотреть, что нашла база (Контекст)"):
                st.write(context_text)

            folder_id = st.secrets["YANDEX_FOLDER_ID"]
            api_key = st.secrets["YANDEX_API_KEY"]
            
            url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
            headers = {
                "Authorization": f"Api-Key {api_key}",
                "Content-Type": "application/json"
            }

            prompt = f"""Ты — помощник по генеалогии. В тексте ниже имена могут быть записаны в виде кортежей, например: ('Иван', 'Рязанцев'). Игнорируй скобки, кавычки и запятые, воспринимай это как обычное имя (Иван Рязанцев). Отвечай на вопрос пользователя, используя ТОЛЬКО предоставленный контекст. Если в контексте нет ответа, скажи 'В данных нет этой информации'.
            
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
