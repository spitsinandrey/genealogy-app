import streamlit as st
import requests
import os
import re
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

# --- ДИЗАЙН ---
st.set_page_config(page_title="Генеалогический помощник", page_icon="🌳", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    h1, h2, h3 { color: #5a6e7f; }
    .stButton>button { background-color: #e6f0fa; color: #4a5d6e; border-radius: 8px; border: 1px solid #c2d6e6; }
    .stButton>button:hover { background-color: #d0e3f5; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌳 Генеалогический ассистент")
st.caption("Выберите дерево для работы или загрузите новое.")

# --- СЛОВАРЬ МЕСЯЦЕВ ---
MONTHS_RU = {
    'JAN': 'января', 'FEB': 'февраля', 'MAR': 'марта', 'APR': 'апреля',
    'MAY': 'мая', 'JUN': 'июня', 'JUL': 'июля', 'AUG': 'августа',
    'SEP': 'сентября', 'OCT': 'октября', 'NOV': 'ноября', 'DEC': 'декабря'
}

def translate_date(date_str):
    if not date_str or date_str.lower() == "неизвестно":
        return "неизвестно"
    
    # Убираем мусор типа @#DJULIAN@
    cleaned = re.sub(r'@#.*?@', '', date_str).strip()
    
    # Ищем английские сокращения месяцев и заменяем на русские
    for eng, rus in MONTHS_RU.items():
        if eng in cleaned.upper():
            # Заменяем только первое вхождение (чтобы не сломать год)
            cleaned = re.sub(eng, rus, cleaned, flags=re.IGNORECASE)
            break
            
    # Добавляем "г." если есть год (4 цифры подряд), но нет слова "г."
    if re.search(r'\d{4}', cleaned) and 'г.' not in cleaned:
        cleaned += ' г.'
        
    return cleaned.strip()

# --- ПАРСИНГ ---
def parse_gedcom(uploaded_file):
    temp_path = f"temp_{uploaded_file.name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    gedcom_parser = Parser()
    gedcom_parser.parse_file(temp_path)
    individuals = [el for el in gedcom_parser.get_element_list() if isinstance(el, IndividualElement)]
    
    people_list = []
    for person in individuals:
        name = person.get_name()
        name_str = " ".join([str(i).replace("'", "").replace('"', '') for i in name if i]) if isinstance(name, tuple) else str(name)
        
        b_date, b_place, d_date, d_place = "неизвестно", "неизвестно", "неизвестно", "неизвестно"
        
        for child in person.get_child_elements():
            if child.get_tag() == 'BIRT':
                for sub in child.get_child_elements():
                    if sub.get_tag() == 'DATE': b_date = translate_date(sub.get_value())
                    if sub.get_tag() == 'PLAC': b_place = sub.get_value()
            if child.get_tag() == 'DEAT':
                for sub in child.get_child_elements():
                    if sub.get_tag() == 'DATE': d_date = translate_date(sub.get_value())
                    if sub.get_tag() == 'PLAC': d_place = sub.get_value()
        
        text = f"Человек: {name_str}. Рождение: {b_date}, Место: {b_place}. Смерть: {d_date}, Место: {d_place}."
        people_list.append(text)
    
    os.remove(temp_path)
    return people_list

# --- УМНЫЙ ПОИСК ---
def smart_search(question, people):
    q_lower = question.lower()
    words = [re.sub(r'[^\w\s]', '', w) for w in q_lower.split() if len(w) > 3]
    
    scored = []
    for doc in people:
        doc_lower = doc.lower()
        first_line = doc_lower.splitlines()[0] if doc_lower else ""
        
        score = 0
        for w in words:
            if w in doc_lower: score += 1
            if w in first_line: score += 3
            
        if "родил" in q_lower or "место рождения" in q_lower:
            birth_block = doc_lower.split("рождение:")[1].split("смерть:")[0] if "рождение:" in doc_lower else ""
            for w in words:
                if w in birth_block: score += 5
                
        if "умер" in q_lower or "смерт" in q_lower:
            death_block = doc_lower.split("смерть:")[1] if "смерть:" in doc_lower else ""
            for w in words:
                if w in death_block: score += 5

        if score > 0:
            scored.append((score, doc))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for s, doc in scored[:5]]
    return []

# --- YANDEX GPT ---
def ask_ai(question, people):
    final_docs = smart_search(question, people)
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

# --- ВКЛАДКИ ---
tab1, tab2 = st.tabs(["🌳 Дерево 1", "🌳 Дерево 2"])

with tab1:
    uploaded_file_1 = st.file_uploader("Загрузите GEDCOM файл (.ged)", type=["ged"], key="upload_1")
    if uploaded_file_1 is not None:
        if "people_1" not in st.session_state:
            with st.spinner("Обрабатываю файл..."):
                st.session_state.people_1 = parse_gedcom(uploaded_file_1)
        st.success(f"Дерево загружено! Найдено человек: {len(st.session_state.people_1)}")
    
    if "people_1" in st.session_state:
        with st.form(key='form_1'):
            question_1 = st.text_input("Ваш вопрос:", placeholder="Например: Кто родился в Кемерово?")
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
            question_2 = st.text_input("Ваш вопрос:", placeholder="Например: Кто родился в Кемерово?")
            submit_2 = st.form_submit_button("Спросить")
        if submit_2 and question_2:
            with st.spinner("Думаю..."):
                answer, context = ask_ai(question_2, st.session_state.people_2)
                st.markdown("### Ответ:")
                st.write(answer)
                if context:
                    with st.expander("🛠️ Что нашла база"):
                        st.write(context)
                    
