# -*- coding: utf-8 -*-
# extract_data.py — создаёт my_family_knowledge.txt
# Один человек = одна запись, с родителями, супругом и детьми.
# Записи разделены маркером ---

import re

# >>> ВАЖНО: укажите здесь точное имя вашего GEDCOM-файла (он в той же папке, что и этот скрипт)
import glob
ged_files = glob.glob("*.ged")
if not ged_files:
    raise SystemExit("GEDCOM-файл (.ged) не найден в этой папке!")
GEDCOM_FILE = ged_files[0]
print(f"Использую файл: {GEDCOM_FILE}")

OUTPUT_FILE = "my_family_knowledge.txt"

MONTHS = {
    "JAN": "января", "FEB": "февраля", "MAR": "марта", "APR": "апреля",
    "MAY": "мая", "JUN": "июня", "JUL": "июля", "AUG": "августа",
    "SEP": "сентября", "OCT": "октября", "NOV": "ноября", "DEC": "декабря",
}
PREFIXES = {"ABT": "около", "BEF": "до", "AFT": "после", "EST": "примерно", "CAL": "примерно"}


def read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def format_date(d):
    if not d:
        return "неизвестно"
    d = re.sub(r"@#D[A-Z]+@", "", d)  # убираем пометки календарей вроде @#DJULIAN@
    d = d.strip()
    prefix = ""
    for k, v in PREFIXES.items():
        if d.upper().startswith(k):
            prefix = v + " "
            d = d[len(k):].strip()
            break
    parts = d.split()
    if len(parts) == 3 and parts[1].upper() in MONTHS:
        return f"{prefix}{int(parts[0])} {MONTHS[parts[1].upper()]} {parts[2]} г."
    if len(parts) == 1 and parts[0].isdigit():
        return f"{prefix}{parts[0]} г." if not prefix else f"{prefix}{parts[0]}"
    return prefix + d.lower()


def split_name(raw):
    s = re.sub(r'["\']', "", raw).strip()
    if "/" in s:
        parts = [p.strip() for p in s.split("/")]
        name = (parts[0] + " " + (parts[1] if len(parts) > 1 else "")).strip()
        rest = "/".join(parts[2:]).strip()
        if rest:
            name = f"{name} ({rest})"
        return name
    return s


def parse_gedcom(path):
    people, families = {}, {}
    cur, cur_type, ctx = None, None, None
    for line in read_text(path).splitlines():
        m = re.match(r"^(\d+)\s+(.*)$", line.strip())
        if not m:
            continue
        level, rest = int(m.group(1)), m.group(2)
        if level == 0:
            mm = re.match(r"^@(.+)@\s+(\w+)\s*$", rest)
            if mm:
                rid = "@" + mm.group(1) + "@"
                cur_type = mm.group(2)
                if cur_type == "INDI":
                    cur = people.setdefault(rid, {"names": [], "birt_date": "", "birt_place": "",
                                                  "deat_date": "", "deat_place": "", "sex": ""})
                elif cur_type == "FAM":
                    cur = families.setdefault(rid, {"husb": [], "wife": [], "chil": []})
                else:
                    cur = None
            else:
                cur, cur_type = None, None
            ctx = None
            continue
        if cur is None:
            continue
        tm = re.match(r"^(\w+)\s*(.*)$", rest)
        tag, value = tm.group(1), tm.group(2).strip()
        if level == 1:
            if tag in ("NAME", "BIRT", "DEAT", "SEX", "HUSB", "WIFE", "CHIL"):
                ctx = tag
            else:
                ctx = None
            if cur_type == "INDI" and tag == "NAME" and value:
                cur["names"].append(value)
            elif cur_type == "INDI" and tag == "SEX":
                cur["sex"] = value
            elif cur_type == "FAM" and tag in ("HUSB", "WIFE", "CHIL") and value:
                cur[tag.lower()].append(value)
        elif level == 2 and cur_type == "INDI" and ctx in ("BIRT", "DEAT"):
            key = "birt" if ctx == "BIRT" else "deat"
            if tag == "DATE":
                cur[key + "_date"] = value
            elif tag == "PLAC":
                cur[key + "_place"] = value
    return people, families


def main():
    people, families = parse_gedcom(GEDCOM_FILE)
    print(f"Прочитано людей: {len(people)}, семей: {families.count if False else len(families)}")

    def name_of(pid):
        rec = people.get(pid)
        if not rec or not rec["names"]:
            return "неизвестный"
        return split_name(rec["names"][0])

    blocks = []
    for pid, rec in people.items():
        name = name_of(pid)
        lines = [f"Человек: {name}."]
        if rec["sex"] == "M":
            lines.append("Пол: мужской.")
        elif rec["sex"] == "F":
            lines.append("Пол: женский.")

        lines.append(f"Рождение: {format_date(rec['birt_date'])}, место: {rec['birt_place'] or 'неизвестно'}.")
        if rec["deat_date"] or rec["deat_place"]:
            lines.append(f"Смерть: {format_date(rec['deat_date'])}, место: {rec['deat_place'] or 'неизвестно'}.")

        parent_lines = []
        for fid, fam in families.items():
            if pid in fam["chil"]:
                for p in fam["husb"]:
                    parent_lines.append("отец: " + name_of(p))
                for p in fam["wife"]:
                    parent_lines.append("мать: " + name_of(p))
        if parent_lines:
            lines.append("Родители: " + ", ".join(parent_lines) + ".")

        spouse_names, child_names = [], []
        role = "Супруг(а)"
        if rec["sex"] == "M":
            role = "Супруга"
        elif rec["sex"] == "F":
            role = "Супруг"
        for fid, fam in families.items():
            if pid in fam["husb"] or pid in fam["wife"]:
                spouse_names += [name_of(p) for p in fam["husb"] + fam["wife"] if p != pid]
                child_names += [name_of(c) for c in fam["chil"]]
        if spouse_names:
            lines.append(f"{role}: " + ", ".join(dict.fromkeys(spouse_names)) + ".")
        if child_names:
            lines.append("Дети: " + ", ".join(dict.fromkeys(child_names)) + ".")

        blocks.append("\n".join(lines))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n---\n".join(blocks) + "\n")

    print(f"Готово! Записей: {len(blocks)}")
    print("Первые 3 записи для проверки:")
    for b in blocks[:3]:
        print("-----")
        print(b)


if __name__ == "__main__":
    main()
