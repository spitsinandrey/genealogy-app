import streamlit as st
import requests
import os
import json
import re
import urllib.parse
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

# --- ДИЗАЙН ---
st.set_page_config(page_title="Генеалогический агент", page_icon="🌳", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    h1, h2, h3 { color: #5a6e7f; }
    .stButton>button { background-color: #e6f0fa; color: #4a5d6e; border-radius: 8px; border: 1px solid #c2d6e6; }
    .stButton>button:hover { background-color: #d0e3f5; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌳 Генеалогический агент")

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

# --- ПАРСИНГ GEDCOM ---
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

# --- УМНЫЙ ПОИСК ПО ДРЕВУ ---
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

# --- ИНСТРУМЕНТЫ АГЕНТА ---
SYSTEM_PROMPT = """Ты — генеалогический ассистент-агент. У тебя есть два инструмента:

1. search_tree — поиск по семейному древу пользователя (GEDCOM). ВСЕГДА начинай с него.
2. open_web_page — открывает веб-страницу и возвращает её текст. Используй, чтобы искать человека в открытых источниках: Память Народа, архивы, метрики.

Правила:
- После search_tree у тебя есть ФИО, даты и место рождения. Сформируй поисковую ссылку сам, например:
  https://pamyat-naroda.ru/heroes/?last_name=Спицин&first_name=Андрей
  и открой её через open_web_page.
- Если страница бесполезна — попробуй другую ссылку или другой запрос.
- Делай НЕ БОЛЬШЕ 4 вызовов инструментов, потом дай финальный ответ.
- Финальный ответ оформи так: что удалось узнать о человеке (из древа и из интернета), а в конце — список использованных ссылок. Если информации нет — так и скажи, не выдумывай.
- Имена в данных могут быть с кавычками и скобками — воспринимай их как обычные имена."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_tree",
            "description": "Поиск по загруженному семейному древу пользователя (GEDCOM). Возвращает карточки людей: ФИО, даты и места рождения/смерти.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос: имя человека и известные детали (фамилия, год, место)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_web_page",
            "description": "Открывает веб-страницу по URL и возвращает её текст (первые 4000 символов). Используй для чтения результатов поиска в открытых источниках.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Полный URL страницы, начиная с https://"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

def run_tool(name, args, people):
    if name == "search_tree":
        docs = smart_search(args.get("query", ""), people)
        if docs:
            return "\n\n".join(docs)
        return "В семейном древе ничего не найдено по этому запросу."

    if name == "open_web_page":
        url = args.get("url", "").strip()
        if not url.startswith("http"):
            return "Ошибка: URL должен начинаться с http:// или https://"
        try:
            r = requests.get("https://r.jina.ai/" + url, timeout=40,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and r.text.strip():
                return r.text[:4000]
        except Exception:
            pass
        try:
            r = requests.get(url, timeout=30,
                             headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            return r.text[:4000] if r.text.strip() else "Страница пуста или не читается."
        except Exception as e:
            return f"Не удалось загрузить страницу: {e}"

    return f"Неизвестный инструмент: {name}"

# --- АГЕНТ (ЦИКЛ С ВЫЗОВОМ ИНСТРУМЕНТОВ) ---
def run_agent(question, people):
    folder_id = st.secrets["YANDEX_FOLDER_ID"]
    api_key = st.secrets["YANDEX_API_KEY"]

    url = "https://llm.api.cloud.yandex.net/v1/chat/completions"
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json",
        "OpenAI-Project": folder_id,
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    trace = []

    for step in range(5):
        payload = {
            "model": f"gpt://{folder_id}/yandexgpt/latest",
            "messages": messages,
            "tools": TOOLS,
            "temperature": 0.2,
            "max_tokens": 2000,
            "stream": False,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if "choices" not in data or not data["choices"]:
            return f"API вернул неожиданный ответ: {json.dumps(data, ensure_ascii=False)[:500]}", trace

        msg = data["choices"][0]["message"]
        if msg.get("content") is None:
            msg["content"] = ""
        messages.append(msg)

        tool_calls = msg.get("tool_calls")

        # Модель решила ответить — цикл закончен
        if not tool_calls:
            return msg.get("content", "Пустой ответ."), trace

        # Выполняем каждый вызов инструмента
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}

            trace.append(f"🔧 Шаг {step + 1}: {fn_name}({json.dumps(args, ensure_ascii=False)})")
            result = run_tool(fn_name, args, people)
            trace.append(f"↩️ Результат: {result[:600]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": result
            })

    return "Не смог собрать ответ за отведённое число шагов. Попробуй уточнить вопрос.", trace

# --- ВКЛАДКИ ---
def render_tree_tab(key):
    st.header(f"🌳 Дерево {key}")
    uploaded_file = st.file_uploader("Загрузите GEDCOM файл (.ged)", type=["ged"], key=f"upload_{key}")

    if uploaded_file is not None:
        if f"people_{key}" not in st.session_state or st.session_state.get(f"file_name_{key}") != uploaded_file.name:
            with st.spinner("Обрабатываю файл..."):
                st.session_state[f"people_{key}"] = parse_gedcom(uploaded_file)
                st.session_state[f"file_name_{key}"] = uploaded_file.name
        st.success(f"Дерево загружено! Найдено человек: {len(st.session_state[f'people_{key}'])}")

    if f"people_{key}" in st.session_state:
        with st.form(key=f'form_{key}'):
            question = st.text_input("Ваш вопрос:", placeholder="Например: Кто такой Андрей Спицин?")
            submit = st.form_submit_button("Спросить")

        if submit and question:
            with st.spinner("Агент ищет в древе и в открытых источниках..."):
                try:
                    answer, trace = run_agent(question, st.session_state[f"people_{key}"])
                    st.markdown("### Ответ:")
                    st.write(answer)

                    if trace:
                        with st.expander("🤔 Как я искал (ход работы агента)"):
                            for line in trace:
                                st.text(line)
                except Exception as e:
                    st.error(f"Произошла ошибка: {e}")

tab1, tab2 = st.tabs(["🌳 Дерево 1", "🌳 Дерево 2"])
with tab1:
    render_tree_tab(1)
with tab2:
    render_tree_tab(2)
