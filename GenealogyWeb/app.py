import streamlit as st
import requests
import os
import re
import urllib.parse
import pandas as pd
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement
from gedcom.element.family import FamilyElement

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

# --- ПАРСИНГ (С созданием графа связей) ---
def parse_gedcom(uploaded_file):
    temp_path = f"temp_{uploaded_file.name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    gedcom_parser = Parser()
    gedcom_parser.parse_file(temp_path)
    root_elements = gedcom_parser.get_element_list()
    
    individuals = [el for el in root_elements if isinstance(el, IndividualElement)]
    families = [el for el in root_elements if isinstance(el, FamilyElement)]
    
    # Словари для быстрого поиска
    id_to_name = {}
    id_to_famc = {}
    id_to_fams = {}
    
    # 1. Собираем базовые данные
    for person in individuals:
        p_id = person.get_pointer()
        name = person.get_name()
        name_str = " ".join([str(i).replace("'", "").replace('"', '') for i in name if i]) if isinstance(name, tuple) else str(name)
        id_to_name[p_id] = name_str
        
        famc = [c.get_value() for c in person.get_child_elements() if c.get_tag() == 'FAMC']
        fams = [c.get_value() for c in person.get_child_elements() if c.get_tag() == 'FAMS']
        id_to_famc[p_id] = famc
        id_to_fams[p_id] = fams

    # 2. Строим граф
    family_graph = {}
    people_list = []
    
    for person in individuals:
        p_id = person.get_pointer()
        name_str = id_to_name[p_id]
        
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

        # Ищем родителей и детей через ID семей
        parents_names = []
        for fam_id in id_to_famc[p_id]:
            for fam in families:
                if fam.get_pointer() == fam_id:
                    # В семье ищем отца и мать
                    for child in fam.get_child_elements():
                        if child.get_tag() == 'HUSB' and child.get_value() in id_to_name:
                            parents_names.append(id_to_name[child.get_value()])
                        if child.get_tag() == 'WIFE' and child.get_value() in id_to_name:
                            parents_names.append(id_to_name[child.get_value()])
                            
        children_names = []
        for fam_id in id_to_fams[p_id]:
            for fam in families:
                if fam.get_pointer() == fam_id:
                    for child in fam.get_child_elements():
                        if child.get_tag() == 'CHIL' and child.get_value() in id_to_name:
                            children_names.append(id_to_name[child.get_value()])
                            
        parents_str = ", ".join(parents_names) if parents_names else "неизвестно"
        children_str = ", ".join(children_names) if children_names else "неизвестно"
        
        family_graph[name_str] = {
            "parents": parents_str,
            "children": children_str,
            "birth_date": b_date,
            "birth_place": b_place,
            "death_date": d_date,
            "death_place": d_place,
            "raw": f"👤 {name_str}. Рождение: {b_date}, Место: {b_place}. Смерть: {d_date}, Место: {d_place}. Родители: {parents_str}. Дети: {children_str}."
        }
        people_list.append(family_graph[name_str]["raw"])
    
    os.remove(temp_path)
    return people_list, family_graph

# --- УМНЫЙ ПОИСК ---
def smart_search(question, people):
    q_lower = question.lower()
    words = [re.sub(r'[^\w\s]', '', w) for w in q_lower.split() if len(w) > 3]
    
    scored = []
    for doc in people:
        doc_lower = doc.lower()
        score = sum(1 for w in words if w in doc_lower)
        if score > 0:
            scored.append((score, doc))
            
    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for s, doc in scored[:5]]
    return []

# --- ПОИСК ПУТИ (Граф) ---
def find_path(start_name, end_name, family_graph):
    if start_name not in family_graph or end_name not in family_graph:
        return None
    
    queue = [[start_name]]
    visited = set()
    
    while queue:
        path = queue.pop(0)
        node = path[-1]
        
        if node == end_name:
            return path
            
        if node not in visited:
            visited.add(node)
            
            # Собираем всех прямых родственников (родители + дети)
            connections = []
            if family_graph[node]["parents"] != "неизвестно":
                connections.extend([p.strip() for p in family_graph[node]["parents"].split(",")])
            if family_graph[node]["children"] != "неизвестно":
                connections.extend([c.strip() for c in family_graph[node]["children"].split(",")])
            
            for conn in connections:
                if conn in family_graph and conn not in visited:
                    new_path = list(path)
                    new_path.append(conn)
                    queue.append(new_path)
    return None

# --- ГЕНЕРАЦИЯ ОТЧЕТОВ ---
def generate_env_report(person_name, family_graph):
    if person_name not in family_graph:
        return "Человек не найден."
    
    p = family_graph[person_name]
    report = f"# ОТЧЕТ ОБ ОКРУЖЕНИИ: {person_name}\n\n"
    report += f"## Блок-персона: {person_name}\n"
    report += f"* **Родился**: {p['birth_date']} ({p['birth_place']})\n"
    report += f"* **Умер**: {p['death_date']} ({p['death_place']})\n\n"
    report += "## Семья\n"
    report += f"* **Родители**: {p['parents']}\n"
    report += f"* **Дети**: {p['children']}\n\n"
    report += "* **Доказательная база**: [Вставьте сканы документов]\n"
    return report

def generate_line_report(path_names, family_graph):
    report = "# ГЕНЕАЛОГИЧЕСКИЙ ОТЧЕТ (ПРЯМАЯ ЛИНИЯ)\n\n"
    report += "## Цепочка поколений\n\n"
    
    for name in path_names:
        # Берем данные из графа напрямую, а не из текста поиска
        if name in family_graph:
            p = family_graph[name]
            report += f"### Блок-персона: {name}\n"
            report += f"* **Родился**: {p['birth_date']} ({p['birth_place']})\n"
            report += f"* **Умер**: {p['death_date']} ({p['death_place']})\n"
            report += f"* **Родители**: {p['parents']}\n"
            report += f"* **Дети**: {p['children']}\n" # Добавил детей для полноты
            report += "* **Доказательная база**: [Вставьте сканы]\n\n"
        else:
            report += f"### Блок-персона: {name}\n(Данные не найдены в графе)\n\n"
            
    return report

# --- YANDEX GPT ---
def ask_ai(question, people):
    final_docs = smart_search(question, people)
    if not final_docs:
        return "В данных нет этой информации.", "Поиск не дал результатов.", []

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
        return answer, context_text, final_docs
    except Exception as e:
        return f"Ошибка API: {e}", context_text, final_docs

# --- ВКЛАДКИ ---
tab1, tab2 = st.tabs(["Проект 1", "Проект 2"])

with tab1:
    proj_name_1 = st.text_input("Название проекта 1:", value="Мое древо 1", key="name_1")
    uploaded_file_1 = st.file_uploader("Загрузите GEDCOM файл (.ged)", type=["ged"], key="upload_1")

    if uploaded_file_1 is not None:
        if "people_1" not in st.session_state:
            with st.spinner("Обрабатываю файл и строю связи..."):
                st.session_state.people_1, st.session_state.graph_1 = parse_gedcom(uploaded_file_1)
    
    if "people_1" in st.session_state:
        st.success(f"[{proj_name_1}] Дерево загружено! Найдено человек: {len(st.session_state.people_1)}")
        
        if "history_1" not in st.session_state: st.session_state.history_1 = []

        for msg in st.session_state.history_1:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if question_1 := st.chat_input("Ваш вопрос...", key="chat_1"):
            st.session_state.history_1.append({"role": "user", "content": question_1})
            with st.chat_message("user"): st.write(question_1)
            
            with st.spinner("Думаю..."):
                answer, context, final_docs = ask_ai(question_1, st.session_state.people_1)
                with st.chat_message("assistant"):
                    st.write(answer)
                    if context:
                        with st.expander("🛠️ Что нашла база"): st.write(context)
                st.session_state.history_1.append({"role": "assistant", "content": answer})

        st.markdown("---")
        st.markdown("### 📊 Генератор отчетов")
        
        report_type = st.radio("Выберите тип отчета:", ["Отчет об окружении", "Генеалогический отчет (Прямая линия)"], horizontal=True)
        
        if report_type == "Отчет об окружении":
            all_names = list(st.session_state.graph_1.keys())
            selected_person = st.selectbox("Выберите персону для отчета:", all_names)
            if st.button("Сформировать Отчет об окружении"):
                report = generate_env_report(selected_person, st.session_state.graph_1)
                st.download_button("📥 Скачать Markdown", data=report.encode('utf-8'), file_name=f"env_{selected_person}.md", mime="text/markdown")
                st.markdown(report)

        elif report_type == "Генеалогический отчет (Прямая линия)":
            all_names = list(st.session_state.graph_1.keys())
            col1, col2 = st.columns(2)
            with col1: start_person = st.selectbox("Прапрадед (Старший):", all_names, key="start_line")
            with col2: end_person = st.selectbox("Праправнук (Младший):", all_names, key="end_line")
            
            if st.button("Построить линию и отчет"):
                path = find_path(start_person, end_person, st.session_state.graph_1)
                if path:
                    st.success(f"Найдена линия: {' -> '.join(path)}")
                    report = generate_line_report(path, st.session_state.graph_1)
                    st.download_button("📥 Скачать Markdown", data=report.encode('utf-8'), file_name=f"line_{start_person}_{end_person}.md", mime="text/markdown")
                    st.markdown(report)
                else:
                    st.warning("Не удалось найти прямую связь между этими людьми.")

        if st.button("🗑️ Очистить историю чата"):
            st.session_state.history_1 = []
            st.rerun()

# Код для tab2 аналогичен tab1, я его сократил для читаемости, но в вашем файле он должен быть полным.
with tab2:
    proj_name_2 = st.text_input("Название проекта 2:", value="Мое древо 2", key="name_2")
    uploaded_file_2 = st.file_uploader("Загрузите GEDCOM файл (.ged)", type=["ged"], key="upload_2")

    if uploaded_file_2 is not None:
        if "people_2" not in st.session_state:
            with st.spinner("Обрабатываю файл и строю связи..."):
                st.session_state.people_2, st.session_state.graph_2 = parse_gedcom(uploaded_file_2)
    
    if "people_2" in st.session_state:
        st.success(f"[{proj_name_2}] Дерево загружено! Найдено человек: {len(st.session_state.people_2)}")
        
        if "history_2" not in st.session_state: st.session_state.history_2 = []

        for msg in st.session_state.history_2:
            with st.chat_message(msg["role"]): st.write(msg["content"])

        if question_2 := st.chat_input("Ваш вопрос...", key="chat_2"):
            st.session_state.history_2.append({"role": "user", "content": question_2})
            with st.chat_message("user"): st.write(question_2)
            
            with st.spinner("Думаю..."):
                answer, context, final_docs = ask_ai(question_2, st.session_state.people_2)
                with st.chat_message("assistant"):
                    st.write(answer)
                    if context:
                        with st.expander("🛠️ Что нашла база"): st.write(context)
                st.session_state.history_2.append({"role": "assistant", "content": answer})

        st.markdown("---")
        st.markdown("### 📊 Генератор отчетов")
        
        report_type_2 = st.radio("Выберите тип отчета:", ["Отчет об окружении", "Генеалогический отчет (Прямая линия)"], horizontal=True, key="radio_2")
        
        if report_type_2 == "Отчет об окружении":
            all_names_2 = list(st.session_state.graph_2.keys())
            selected_person_2 = st.selectbox("Выберите персону для отчета:", all_names_2, key="person_2")
            if st.button("Сформировать Отчет об окружении", key="btn_env_2"):
                report = generate_env_report(selected_person_2, st.session_state.graph_2)
                st.download_button("📥 Скачать Markdown", data=report.encode('utf-8'), file_name=f"env_{selected_person_2}.md", mime="text/markdown")
                st.markdown(report)

        elif report_type_2 == "Генеалогический отчет (Прямая линия)":
            all_names_2 = list(st.session_state.graph_2.keys())
            col1, col2 = st.columns(2)
            with col1: start_person_2 = st.selectbox("Прапрадед (Старший):", all_names_2, key="start_line_2")
            with col2: end_person_2 = st.selectbox("Праправнук (Младший):", all_names_2, key="end_line_2")
            
            if st.button("Построить линию и отчет", key="btn_line_2"):
                path = find_path(start_person_2, end_person_2, st.session_state.graph_2)
                if path:
                    st.success(f"Найдена линия: {' -> '.join(path)}")
                    report = generate_line_report(path, st.session_state.graph_2)
                    st.download_button("📥 Скачать Markdown", data=report.encode('utf-8'), file_name=f"line_{start_person_2}_{end_person_2}.md", mime="text/markdown")
                    st.markdown(report)
                else:
                    st.warning("Не удалось найти прямую связь между этими людьми.")

        if st.button("🗑️ Очистить историю чата", key="clear_2"):
            st.session_state.history_2 = []
            st.rerun()
