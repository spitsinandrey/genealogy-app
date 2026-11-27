import streamlit as st
import requests
import os
import re
import urllib.parse
import pandas as pd
import io
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

# --- СЛОВАРЬ МЕСЯЦЕВ ---
MONTHS_RU = {
    'JAN': 'января', 'FEB': 'февраля', 'MAR': 'марта', 'APR': 'апреля',
    'MAY': 'мая', 'JUN': 'июня', 'JUL': 'июля', 'AUG': 'августа',
    'SEP': 'сентября', 'OCT': 'октября', 'NOV': 'ноября', 'DEC': 'декабря'
}

def translate_date(date_str):
    if not date_str or date_str.lower() == "неизвестно":
        return "неизвестно"
    cleaned = re.sub(r'@#.*?@', '', date_str).strip()
    for eng, rus in MONTHS_RU.items():
        if eng in cleaned.upper():
            cleaned = re.sub(eng, rus, cleaned, flags=re.IGNORECASE)
            break
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
        
        text = f"👤 {name_str}. Рождение: {b_date}, Место: {b_place}. Смерть: {d_date}, Место: {d_place}."
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

# --- ИЗВЛЕЧЕНИЕ ДАННЫХ ДЛЯ ПОИСКА ---
def extract_search_data(context_text):
    first_line = context_text.split("\n")[0]
    name_match = re.search(r'👤\s*(.*?)\.', first_line)
    name = name_match.group(1).strip() if name_match else ""
    birth_match = re.search(r'Рождение:\s*.*?(\d{4})', first_line)
    birth_year = birth_match.group(1) if birth_match else ""
    place_match = re.search(r'Рождение:.*?Место:\s*(.*?)\.', first_line)
    place = place_match.group(1).strip() if place_match else ""
    if place == "неизвестно": place = ""
    return name, birth_year, place

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

# --- ФУНКЦИЯ ВЫГРУЗКИ В CSV (Исправленная) ---
def get_csv_data(context_text):
    lines = context_text.split("\n\n")
    data = []
    for line in lines:
        if not line.strip(): continue
        
        # Строгий парсинг
        name_match = re.search(r'👤\s*(.*?)\.', line)
        birth_match = re.search(r'Рождение:\s*(.*?), Место:\s*(.*?)\.', line)
        death_match = re.search(r'Смерть:\s*(.*?), Место:\s*(.*?)\.', line)
        
        data.append({
            "Имя": name_match.group(1) if name_match else "",
            "Дата рождения": birth_match.group(1) if birth_match else "неизвестно",
            "Место рождения": birth_match.group(2) if birth_match else "неизвестно",
            "Дата смерти": death_match.group(1) if death_match else "неизвестно",
            "Место смерти": death_match.group(2) if death_match else "неизвестно"
        })
    # Возвращаем DataFrame с разделителем ';' для Excel
    return pd.DataFrame(data)

# --- ВКЛАДКИ ---
tab1, tab2 = st.tabs(["Проект 1", "Проект 2"])

with tab1:
    # Поле для названия проекта
    proj_name_1 = st.text_input("Название проекта 1:", value="Мое древо 1", key="name_1")
    uploaded_file_1 = st.file_uploader("Загрузите GEDCOM файл (.ged)", type=["ged"], key="upload_1")

    if uploaded_file_1 is not None:
        if "people_1" not in st.session_state:
            with st.spinner("Обрабатываю файл..."):
                st.session_state.people_1 = parse_gedcom(uploaded_file_1)
    
    if "people_1" in st.session_state:
        st.success(f"[{proj_name_1}] Дерево загружено! Найдено человек: {len(st.session_state.people_1)}")
        
        # Инициализация истории чата
        if "history_1" not in st.session_state:
            st.session_state.history_1 = []

        # Отображение истории
        for msg in st.session_state.history_1:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # Поле ввода вопроса (чат-стиль)
        if question_1 := st.chat_input("Ваш вопрос...", key="chat_1"):
            st.session_state.history_1.append({"role": "user", "content": question_1})
            with st.chat_message("user"):
                st.write(question_1)
            
            with st.spinner("Думаю..."):
                answer, context = ask_ai(question_1, st.session_state.people_1)
                
                with st.chat_message("assistant"):
                    st.write(answer)
                    
                    if context:
                        st.markdown("---")
                        st.markdown("**🔍 Поискать в открытых источниках:**")
                        p_name, p_year, p_place = extract_search_data(context)
                        
                        if p_name:
                            pn_lastname = p_name.split()[-1] if p_name else ""
                            pn_firstname = p_name.split()[0] if p_name else ""
                            full_query = f"{p_name} {p_year} {p_place}".strip()
                            
                            url_pn = f"https://pamyat-naroda.ru/heroes/?last_name={urllib.parse.quote(pn_lastname)}&first_name={urllib.parse.quote(pn_firstname)}&date_birth={p_year}&place_birth={urllib.parse.quote(p_place)}"
                            url_ya = f"https://ya.ru/archive/search?text={urllib.parse.quote(full_query)}"
                            url_fs = f"https://www.familysearch.org/search/record/results?q.givenName={urllib.parse.quote(pn_firstname)}&q.surname={urllib.parse.quote(pn_lastname)}&q.birthLikeDate.from={p_year}&q.birthLikePlace={urllib.parse.quote(p_place)}"
                            url_gwar = f"https://gwar.mil.ru/heroes/?last_name={urllib.parse.quote(pn_lastname)}&first_name={urllib.parse.quote(pn_firstname)}"
                            url_familio = f"https://familio.org/search?query={urllib.parse.quote(full_query)}"
                            url_openlist = f"https://ru.openlist.wiki/index.php?title=Служебная:Поиск&search={urllib.parse.quote(full_query)}"
                            url_barak = f"https://bessmertnybarak.com/search/?q={urllib.parse.quote(full_query)}"

                            r1_col1, r1_col2, r1_col3 = st.columns(3)
                            with r1_col1: st.link_button("🇷🇺 Память Народа", url_pn)
                            with r1_col2: st.link_button("🌍 FamilySearch", url_fs)
                            with r1_col3: st.link_button("📜 Архивы Яндекса", url_ya)
                                
                            r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)
                            with r2_col1: st.link_button("⚔️ Первая Мировая", url_gwar)
                            with r2_col2: st.link_button("🌳 Familio", url_familio)
                            with r2_col3: st.link_button("📖 Открытый список", url_openlist)
                            with r2_col4: st.link_button("🕯️ Бессмертный барак", url_barak)

                            df = get_csv_data(context)
                            csv = df.to_csv(index=False, sep=';').encode('utf-8-sig')
                            st.download_button(
                                label="📥 Скачать результаты (CSV)",
                                data=csv,
                                file_name='found_people.csv',
                                mime='text/csv',
                            )
                    
                        with st.expander("🛠️ Что нашла база"):
                            st.write(context)
                            
                st.session_state.history_1.append({"role": "assistant", "content": answer})

        # Кнопка очистки истории
        if st.button("🗑️ Очистить историю"):
            st.session_state.history_1 = []
            st.rerun()

with tab2:
    # Поле для названия проекта
    proj_name_2 = st.text_input("Название проекта 2:", value="Мое древо 2", key="name_2")
    uploaded_file_2 = st.file_uploader("Загрузите GEDCOM файл (.ged)", type=["ged"], key="upload_2")

    if uploaded_file_2 is not None:
        if "people_2" not in st.session_state:
            with st.spinner("Обрабатываю файл..."):
                st.session_state.people_2 = parse_gedcom(uploaded_file_2)
    
    if "people_2" in st.session_state:
        st.success(f"[{proj_name_2}] Дерево загружено! Найдено человек: {len(st.session_state.people_2)}")
        
        if "history_2" not in st.session_state:
            st.session_state.history_2 = []

        for msg in st.session_state.history_2:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if question_2 := st.chat_input("Ваш вопрос...", key="chat_2"):
            st.session_state.history_2.append({"role": "user", "content": question_2})
            with st.chat_message("user"):
                st.write(question_2)
            
            with st.spinner("Думаю..."):
                answer, context = ask_ai(question_2, st.session_state.people_2)
                
                with st.chat_message("assistant"):
                    st.write(answer)
                    
                    if context:
                        st.markdown("---")
                        st.markdown("**🔍 Поискать в открытых источниках:**")
                        p_name, p_year, p_place = extract_search_data(context)
                        
                        if p_name:
                            pn_lastname = p_name.split()[-1] if p_name else ""
                            pn_firstname = p_name.split()[0] if p_name else ""
                            full_query = f"{p_name} {p_year} {p_place}".strip()
                            
                            url_pn = f"https://pamyat-naroda.ru/heroes/?last_name={urllib.parse.quote(pn_lastname)}&first_name={urllib.parse.quote(pn_firstname)}&date_birth={p_year}&place_birth={urllib.parse.quote(p_place)}"
                            url_ya = f"https://ya.ru/archive/search?text={urllib.parse.quote(full_query)}"
                            url_fs = f"https://www.familysearch.org/search/record/results?q.givenName={urllib.parse.quote(pn_firstname)}&q.surname={urllib.parse.quote(pn_lastname)}&q.birthLikeDate.from={p_year}&q.birthLikePlace={urllib.parse.quote(p_place)}"
                            url_gwar = f"https://gwar.mil.ru/heroes/?last_name={urllib.parse.quote(pn_lastname)}&first_name={urllib.parse.quote(pn_firstname)}"
                            url_familio = f"https://familio.org/search?query={urllib.parse.quote(full_query)}"
                            url_openlist = f"https://ru.openlist.wiki/index.php?title=Служебная:Поиск&search={urllib.parse.quote(full_query)}"
                            url_barak = f"https://bessmertnybarak.com/search/?q={urllib.parse.quote(full_query)}"

                            r1_col1, r1_col2, r1_col3 = st.columns(3)
                            with r1_col1: st.link_button("🇷🇺 Память Народа", url_pn)
                            with r1_col2: st.link_button("🌍 FamilySearch", url_fs)
                            with r1_col3: st.link_button("📜 Архивы Яндекса", url_ya)
                                
                            r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)
                            with r2_col1: st.link_button("⚔️ Первая Мировая", url_gwar)
                            with r2_col2: st.link_button("🌳 Familio", url_familio)
                            with r2_col3: st.link_button("📖 Открытый список", url_openlist)
                            with r2_col4: st.link_button("🕯️ Бессмертный барак", url_barak)

                            df = get_csv_data(context)
                            csv = df.to_csv(index=False, sep=';').encode('utf-8-sig')
                            st.download_button(
                                label="📥 Скачать результаты (CSV)",
                                data=csv,
                                file_name='found_people.csv',
                                mime='text/csv',
                            )
                    
                        with st.expander("🛠️ Что нашла база"):
                            st.write(context)
                            
                st.session_state.history_2.append({"role": "assistant", "content": answer})

        if st.button("🗑️ Очистить историю"):
            st.session_state.history_2 = []
            st.rerun()
