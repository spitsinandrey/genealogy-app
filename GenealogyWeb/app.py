def generate_line_report(path_names, family_graph):
    report = "# ГЕНЕАЛОГИЧЕСКИЙ ОТЧЕТ (ПРЯМАЯ ЛИНИЯ)\n\n"
    report += "## Цепочка поколений\n\n"
    
    for i, name in enumerate(path_names):
        if name in family_graph:
            p = family_graph[name]
            
            # Определяем родителя и ребенка СТРОГО по цепочке
            parent_in_line = path_names[i-1] if i > 0 else "Неизвестен (начало линии)"
            child_in_line = path_names[i+1] if i < len(path_names)-1 else "Неизвестен (конец линии)"
            
            report += f"### Блок-персона: {name}\n"
            report += f"* **Родился**: {p['birth_date']} ({p['birth_place']})\n"
            report += f"* **Умер**: {p['death_date']} ({p['death_place']})\n"
            
            # Выводим только тех, кто в линии
            report += f"* **Родитель (по линии)**: {parent_in_line}\n"
            report += f"* **Ребенок (по линии)**: {child_in_line}\n"
            
            report += "* **Доказательная база**: [Вставьте сканы]\n\n"
        else:
            report += f"### Блок-персона: {name}\n(Данные не найдены)\n\n"
            
    return report
