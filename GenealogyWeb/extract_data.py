# -*- coding: utf-8 -*-
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

# Файл лежит в этой же папке
file_path = r"Familio_gedcom_2026-09-03_11-00-15 (1).ged"
# Сохраняем результат сюда же, в сетевую папку
output_file = r"my_family_knowledge.txt"

def get_event_info(person, event_tag):
    date = "неизвестно"
    place = "неизвестно"
    for child in person.get_child_elements():
        if child.get_tag() == event_tag:
            for subchild in child.get_child_elements():
                if subchild.get_tag() == 'DATE':
                    date = subchild.get_value()
                elif subchild.get_tag() == 'PLAC':
                    place = subchild.get_value()
    return date, place

try:
    print("Читаем файл...")
    gedcom_parser = Parser()
    gedcom_parser.parse_file(file_path)
    
    root_elements = gedcom_parser.get_element_list()
    individuals = [element for element in root_elements if isinstance(element, IndividualElement)]
    
    print(f"Найдено {len(individuals)} человек. Создаем базу знаний...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for person in individuals:
            name_tuple = person.get_name()
            name_str = " ".join([str(i) for i in name_tuple if i])
            
            b_date, b_place = get_event_info(person, 'BIRT')
            d_date, d_place = get_event_info(person, 'DEAT')
            
            text = f"Человек: {name_str}.\n"
            text += f"Рождение: {b_date}, Место: {b_place}.\n"
            text += f"Смерть: {d_date}, Место: {d_place}.\n"
            
            famc = [c.get_value() for c in person.get_child_elements() if c.get_tag() == 'FAMC']
            if famc:
                text += f"ID семьи родителей: {', '.join(famc)}.\n"
                
            text += "---\n"
            f.write(text)

    print(f"Готово! Все данные сохранены в файл: {output_file}")

except Exception as e:
    print(f"Произошла ошибка: {e}")