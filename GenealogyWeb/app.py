import streamlit as st
import requests
import os
from difflib import SequenceMatcher

st.set_page_config(page_title="Генеалогический помощник", page_icon="🌳")
st.title("🌳 Чат с вашим древом")
st.caption("Задайте вопрос. Я найду ответ в ваших файлах GEDCOM.")

BASE_DIR = os.path.dirname(__file__)
TXT_PATH = os.path.join(BASE_DIR, "my_family_knowledge.txt")


@st.cache_data
def load_people():
    # Один человек = один документ (разделяем по маркеру ---)
    with open(TXT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return [p.strip() for p in content.split("---") if p.strip()]


try:
    people = load_people()
except FileNotFoundError:
    st.error(f"Файл не найден по пути: {TXT_PATH}")
    st.stop()

if not people:
    st.error("Файл базы знаний пуст.")
    st.stop()

st.success(f"База знаний загружена! Найдено человек: {len(people)}")

with st.form("my_form"):
    question = st.text_input("Ваш вопрос:", placeholder="Например: Кто такой Андрей Спицин?")
    submitted = st.form_submit_button("Спросить")

if submitted and question:
    with st.spinner("Ищу в дереве и думаю над ответом..."):
        try:
            # --- УМНЫЙ ПОИСК (лёгкий, без нейросети-эмбеддера) ---
            words_to_find = [w.lower().strip("?.,!«»\"'") for w in question.split() if len(w) > 3]

            scored = 
            for doc in people:
                doc_lower = doc.lower()
                # Безопасное получение первой строки
                lines = doc_lower.splitlines()
                first_line = lines if lines else ""
                
                score = sum(1 for w in words_to_find if w in doc_lower)
                # Бонус, если слова из вопроса есть в самом имени человека
                score += 2 * sum(1 for w in words_to_find if w in first_line)
                
                if score > 0:
                    scored.append((score, doc))

            if scored:
                scored.sort(key=lambda x: x, reverse=True)
                final_docs = [doc for s, doc in scored[:5]]
                search_type = "Точный поиск по словам"
            else:
                # Резервный поиск: сравниваем вопрос с именами по похожести
                q = question.lower()
                fuzzy = sorted(
                    people,
                    key=lambda d: SequenceMatcher(None, q, (d.splitlines().lower() if d else "")).ratio(),
                    reverse=True,
                )[:5]
                best_line = fuzzy.splitlines().lower() if fuzzy else ""
                if fuzzy and SequenceMatcher(None, q, best_line).ratio() > 0.45:
                    final_docs = fuzzy
                    search_type = "Поиск по похожести имени"
                else:
                    final_docs = 
                    search_type = "Ничего не найдено"

            if final_docs:
                context_text = "\n\n".join(final_docs)
                with st.expander(f"🛠️ Что нашла база ({search_type})"):
                    st.write(context_text)
            else:
                st.markdown("### Ответ:")
                st.write("В данных нет этой информации.")
                st.stop()

            folder_id = st.secrets["YANDEX_FOLDER_ID"]
            api_key = st.secrets["YANDEX_API_KEY"]

            url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
            headers = {
                "Authorization": f"Api-Key {api_key}",
                "Content-Type": "application/json"
            }

            prompt = f"""Ты — помощник по генеалогии. В тексте имена людей могут быть записаны с кавычками, скобками и запятыми — игнорируй их и воспринимай запись как обычное имя. Отвечай на вопрос пользователя, используя ТОЛЬКО предоставленный контекст. Если в контексте нет ответа, скажи 'В данных нет этой информации'.

Контекст:
{context_text}

Вопрос: {question}
Ответ:"""

            payload = {
                "modelUri": f"gpt://{folder_id}/yandexgpt-lite/latest",
                "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": 1000},
                "messages": [{"role": "user", "text": prompt}]
            }

            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            data
