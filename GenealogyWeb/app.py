import streamlit as st
import requests
import os
from difflib import SequenceMatcher
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

st.set_page_config(page_title="Генеалогический помощник", page_icon="🌳")
st.title("🌳 Чат с вашим древом")
st.caption("Загрузите GEDCOM-файл и задавайте вопросы.")

# --- ФУНКЦИЯ ПАРСИНГА GEDCOM ---
def parse_gedcom(uploaded_file):
    # Сохраняем загруженный файл во временный
    temp_path = "temp_uploaded.ged"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    gedcom_parser = Parser()
    gedcom_parser.parse_file(temp_path)
    root_elements = gedcom_parser.get_element_list()
    individuals = [el for el in root_elements if isinstance(el, IndividualElement)]
    
    people_list = []
    for person in individuals:
        name = person.get_name()
        # Очищаем имя
        if isinstance(name, tuple):
            name_str = " ".join([str(i).replace("'", "").replace('"', '') for i in name if i])
        else:
            name_str = str(name).replace("'", "").replace('"', '')
        
        # Ищем события (рождение/смерть)
        b_date, b_place = "неизвестно", "неизвестно"
        d_date, d_place = "неизвестно", "неизвестно"
        
        for child in person.get_child_elements():
            if child.get_tag() == 'BIRT':
                for sub in child.get_child_elements():
                    if sub.get_tag() == 'DATE': b_date = sub.get_value()
                    if sub.get_tag() == 'PLAC': b_place = sub.get_value()
            if child.get_tag() == 'DEAT':
                for sub in child.get_child_elements():
                    if sub.get_tag() == 'DATE': d_date = sub.get_value()
                    if sub.get_tag() == 'PLAC': d_place = sub.get_value()
        
        text = f"Человек: {name_str}. Рождение: {b_date}, Место: {b_place}. Смерть: {d_date}, Место: {d_place}."
        people_list.append(text)
    
    os.remove(temp_path) # Удаляем временный файл
    return people_list

# --- ЗАГРУЗКА ФАЙЛА ---
uploaded_file = st.file_uploader("Загрузите ваш GEDCOM файл (.ged)", type=["ged"])

if uploaded_file is not None:
    with st.spinner("Обрабатываю ваш файл..."):
        if "people" not in st.session_state:
            st.session_state.people = parse_gedcom(uploaded_file)
        people = st.session_state.people
    st.success(f"Файл загружен! Найдено человек: {len(people)}")
else:
    st.info("Пожалуйста, загрузите файл .ged, чтобы начать.")
    st.stop()

# --- ПОИСК И ЧАТ ---
with st.form("my_form"):
    question = st.text_input("Ваш вопрос:", placeholder="Например: Кто такой Андрей Спицин?")
    submitted = st.form_submit_button("Спросить")

if submitted and question:
    with st.spinner("Ищу в дереве..."):
        try:
            words_to_find = [w.lower().strip("?.,!«»\"'") for w in question.split() if len(w) > 3]
            scored = []
            
            for doc in people:
                doc_lower = doc.lower()
                first_line = doc_lower.splitlines()[0] if doc_lower else ""
                score = sum(1 for w in words_to_find if w in doc_lower)
                score += 2 * sum(1 for w in words_to_find if w in first_line)
                if score > 0:
                    scored.append((score, doc))

            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                final_docs = [doc for s, doc in scored[:5]]
                search_type = "Точный поиск"
            else:
                final_docs = []
                search_type = "Ничего не найдено"

            if final_docs:
                context_text = "\n\n".join(final_docs)
                with st.expander(f"🛠️ Контекст ({search_type})"):
                    st.write(context_text)
            else:
                st.markdown("### Ответ:")
                st.write("В данных нет этой информации.")
                st.stop()

            # --- ЗАПРОС К YANDEX GPT ---
            folder_id = st.secrets["YANDEX_FOLDER_ID"]
            api_key = st.secrets["YANDEX_API_KEY"]
            url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
            headers = {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}

            prompt = f"""Ты — помощник по генеалогии. Отвечай на вопрос, используя ТОЛЬКО контекст. Если нет ответа, скажи 'В данных нет этой информации'.
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
            answer = response.json()['result']['alternatives'][0]['message']['text']
            st.markdown("### Ответ:")
            st.write(answer)

        except Exception as e:
            st.error(f"Ошибка: {e}")
