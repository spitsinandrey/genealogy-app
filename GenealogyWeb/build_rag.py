# -*- coding: utf-8 -*-
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

print("1. Загружаем текстовый файл...")
loader = TextLoader(r"\\26.255.202.96\общая папка\1 A  ЛИЧНЫЕ ПАПКИ\Спицин А.Е\Личное\Генеология\my_family_knowledge.txt", encoding="utf-8")
documents = loader.load()

print("2. Разбиваем текст на куски (чанки)...")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = text_splitter.split_documents(documents)
print(f"   Получилось {len(chunks)} кусочков текста.")

print("3. Загружаем модель эмбеддингов (перевод текста в цифры)...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

print("4. Создаем векторную базу данных (сохраняем в папку chroma_db)...")
vectorstore = Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory="C:/Users/pgkm-yurist/chroma_db_genealogy")

print("--- ГОТОВО! Векторная база данных успешно создана и сохранена. ---")