# -*- coding: utf-8 -*-
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

# Путь к вашему файлу
file_path = r"\\26.255.202.96\общая папка\1 A  ЛИЧНЫЕ ПАПКИ\Спицин А.Е\Личное\Генеология\Familio_gedcom_2026-09-03_11-00-15 (1).ged"

try:
    gedcom_parser = Parser()
    gedcom_parser.parse_file(file_path)
    
    print("--- Файл успешно прочитан! ---")
    
    root_elements = gedcom_parser.get_element_list()
    individuals = [element for element in root_elements if isinstance(element, IndividualElement)]
    
    print(f"Всего людей в дереве: {len(individuals)}")
    
    print("\nПервые 5 записей:")
    for person in individuals[:5]:
        name = person.get_name()
        surname = person.get_surname() if hasattr(person, 'get_surname') else ""
        
        full_name = f"- {name} {surname}".strip()
        print(full_name)

except FileNotFoundError:
    print(f"ОШИБКА: Файл не найден по пути: {file_path}")
except Exception as e:
    print(f"Произошла ошибка: {e}")