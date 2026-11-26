import streamlit as st
import requests
import os
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

# --- НАСТРОЙКА ДИЗАЙНА ---
st.set_page_config(page_title="Генеалогический помощник", page_icon="🌳", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    h1, h2, h3 { color: #5a6e7f; }
    .stButton>button { background-color: #e6f0fa; color: #4a5d6e; border-radius: 8px; border: 1px solid #c2d6e6; }
    .stButton>button:hover { background-color: #d0e3f5; }
    .stTextInput>div>div>input { border-radius: 8px; border: 1px solid #dcdcdc; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌳 Генеалогический ассистент")
st.caption("Выберите дерево для работы или загрузите новое.")

# --- ФУНКЦИЯ ПАРСИНГА GEDCOM ---
def parse_gedcom(uploaded_file):
    temp_path = f"temp_{uploaded_file.name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    gedcom_parser = Parser()
    gedcom_parser.parse_file(temp_path)
    root_elements = gedcom_parser.get_element_list()
    individuals = [el for el in root_elements if isinstance(el, IndividualElement)]
    
    people_list = []
    for person in individuals:
        name = person.get_name()
        if isinstance(name, tuple):
            name_str = " ".join([str(i).replace("'", "").replace('"', '') for i in name if i])
        else:
            name_str = str(name).replace("'", "").replace('"', '')
        
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
    
    os.remove(temp_path)
    return people_list

# --- ФУНКЦИЯ ЗАПРОСА К YANDEX GPT ---
def ask_ai(question, people):
    words_to_find = [w.lower().strip("?.,!«»\"'") for w in question.split() if len(w) > 3]
    scored = []
    
    for doc in people:
        doc_lower = doc.lower()
        first_line = doc_lower.splitlines()[0] if doc_lower else ""
        
        # Считаем совпадения
        score = sum(1 for w in words_to_find if w in doc_lower)
        # Даем большой бонус (х3), если слово из вопроса есть в самом имени (первой строке)
        score += 3 * sum(1 for w in words_to_find if w in first_line)
        
        if score > 0:
            scored.append((score, doc))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        final_docs = [doc for s, doc in scored[:5]]
    else:
        final_docs = []

    if not final_docs:
        return "В данных нет этой информации.", "Поиск не дал результатов."

    context_text = "\n\n".join(final_docs)
    
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

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        answer = response.json()['result']['alternatives'][0]['message']['text']
        return answer, context_text
    except Exception as e:
        return f"Ошибка API: {e}", context_text

# --- ЛОГИКА ВКЛАДОК ---
tab1, tab2 = st.tabs(["🌳 Дерево 1", "🌳 Дерево 2"])

with tab1:
    uploaded_file_1 = st.file_uploader("Загрузите GEDCOM файл (.ged)", type=["ged"], key="upload_1")
    
    if uploaded_file_1 is not None:
        if "people_1" not in st.session_state:
            with st.spinner("Обрабатываю файл..."):
                st.session_state.people_1 = parse_gedcom(uploaded_file_1)
        st.success(f"Дерево загружено! Найдено человек: {len(st.session_state.people_1)}")
    
    if "people_1" in st.session_state:
        # Используем форму, чтобы избежать перезагрузки страницы
        with st.form(key='form_1'):
            question_1 = st.text_input("Ваш вопрос:", placeholder="Например: Кто такой Андрей Спицин?")
            submit_1 = st.form_submit_button("Спросить")
            
        if submit_1 and question_1:
            with st.spinner("Думаю..."):
                answer, context = ask_ai(question_1, st.session_state.people_1)
                st.markdown("### Ответ:")
                st.write(answer)
                if context:
                    with st.expander("🛠️ Что нашла база"):
                        st.write(context)

with tab2:
    uploaded_file_2 = st.file_uploader("Загрузите GEDCOM файл (.ged)", type=["ged"], key="upload_2")
    
    if uploaded_file_2 is not None:
        if "people_2" not in st.session_state:
            with st.spinner("Обрабатываю файл..."):
                st.session_state.people_2 = parse_gedcom(uploaded_file_2)
        st.success(f"Дерево загружено! Найдено человек: {len(st.session_state.people_2)}")
    
    if "people_2" in st.session_state:
        with st.form(key='form_2'):
            question_2 = st.text_input("Ваш вопрос:", placeholder="Введите вопрос...")
            submit_2 = st.form_submit_button("Спросить")
            
        if submit_2 and question_2:
            with st.spinner("Думаю..."):
                answer, context = ask_ai(question_2, st.session_state.people_2)
                st.markdown("### Ответ:")
                st.write(answer)
                if context:
                    with st.expander("🛠️ Что нашла база"):
                        st.write(context)
