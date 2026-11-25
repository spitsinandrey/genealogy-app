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

if
