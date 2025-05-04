# Dependencies
import functools
import json
import logging
import re


from pydantic import BaseModel, field_validator, ValidationError
import PyPDF2
from rich import print

from models.PlayEvent import GameEvent

# Const. Vars
PATH_PDF = "data/raw/stats_pwss2402.pdf"
PATH_JSON = "data/interim/stats_pwss2402.json"
CALL_COUNTS = {}

# Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(f"{__name__}.log")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Funcs
def log_function_name(func):
    """Decorator, der den Namen der aufgerufenen Funktion ausgibt und die Aufrufanzahl zählt."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        CALL_COUNTS[func.__name__] = CALL_COUNTS.get(func.__name__, 0) + 1
        # print(f"Aufruf der Funktion: {func.__name__} (Aufrufe: {CALL_COUNTS[func.__name__]})")
        return func(*args, **kwargs)

    return wrapper


def _is_letter_dominant(string: str) -> bool:
    letters = sum(c.isalpha() for c in string)
    digits = sum(c.isdigit() for c in string)
    special_chars = sum(not c.isalnum() for c in string)

    return letters > (digits + special_chars)


#######################################################
#########                 IO                  #########
#######################################################


def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text_per_page = []
        for page in reader.pages:
            text_per_page.append(page.extract_text())
    return text_per_page


def save_dict_to_json(data: dict, file_path: str, indent: int = 4):
    """
    Speichert ein Python-Dictionary als JSON-Datei.

    :param data: Das Dictionary, das gespeichert werden soll.
    :param file_path: Der Pfad zur JSON-Datei.
    :param indent: Anzahl der Leerzeichen für die Formatierung (Default: 4).
    """
    try:
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(data, json_file, indent=indent, ensure_ascii=False)
        print(f"Datei erfolgreich gespeichert: {file_path}")
    except Exception as e:
        print(f"Fehler beim Speichern der Datei: {e}")


#######################################################
#########               Parse                 #########
#######################################################

def remove_drive_start_info(drive: str) -> str:
    """
    Entfernt die ersten drei Key-Value-Paare aus dem Drive-String und stellt sicher, 
    dass der bereinigte String mit zwei Großbuchstaben und einer Zahl&Zahl beginnt.

    Diese Funktion sucht nach einem vordefinierten Muster am Anfang des Drive-Strings,
    entfernt es und gibt den bereinigten String zurück. Wenn das Muster nicht gefunden wird, 
    wird der ursprüngliche String zurückgegeben.

    Parameters
    ----------
    drive : str
        Der Input-Drive-String, der die Informationen enthält, die entfernt werden sollen.

    Returns
    -------
    str
        Der bereinigte Drive-String ohne die ersten drei Key-Value-Paare. 
        Wenn das Muster nicht gefunden wird, wird der ursprüngliche String zurückgegeben.

    Notes
    -----
    Diese Funktion erwartet, dass der Drive-String ein spezifisches Format hat, 
    das zwei Großbuchstaben gefolgt von einer Zahl&Zahl am Anfang des bereinigten 
    Strings enthält.
    """
    
    # Regular Expression zum Finden der ersten drei Key-Value-Paare und deren Werte
    pattern = r'^[A-Za-z\s]+(Spot:\s+\w+\s+Clock:\s+\d{2}:\d{2}\s+Drive:\s+\d+)\s*'
    match = re.match(pattern, drive)

    if match:
        # Entfernen der erkannten Teile
        cleaned_string = drive[match.end():].strip()
        # Sicherstellen, dass der String mit zwei Großbuchstaben und einer Zahl&Zahl beginnt
        cleaned_string = cleaned_string.lstrip()
        cleaned_string = re.sub(r'^[^A-Z]*([A-Z]{2}\s*\d+&\d+)', r'\1', cleaned_string)
        return cleaned_string
    return drive.strip()


def remove_drive_summary(drive: str) -> str:
    """
    Entfernt die Zusammenfassungsinformationen aus dem Drive-String.

    Diese Funktion sucht nach einem vordefinierten Muster, das die 
    Zusammenfassungsinformationen wie "Plays", "Yards", "TOP", 
    und "SCORE" enthält, und entfernt diese aus dem gegebenen 
    Drive-String. 

    Parameters
    ----------
    drive : str
        Der Input-Drive-String, der die Zusammenfassungsinformationen enthält, 
        die entfernt werden sollen.

    Returns
    -------
    str
        Der bereinigte Drive-String ohne die Zusammenfassungsinformationen. 

    Notes
    -----
    Diese Funktion erwartet, dass der Drive-String ein spezifisches Format 
    hat, das die Zusammenfassungsinformationen in der beschriebenen Weise 
    enthält.
    """

    # Regular Expression zum Finden der Summary und deren Werte
    pattern = r'\s*Plays\s+\d+\s+Yards\s+\d+\s+TOP\s+\d{2}:\d{2}\s+SCORE\s*[\d-]*'
    cleaned_string = re.sub(pattern, '', drive)
    return cleaned_string.strip()


def parse_from_str_to_drive(input_string: str):
    # Entferne wiederholte Großbuchstaben (z.B. "VV VV" -> "VV")
    input_string = re.sub(r"(\b[A-Z]{2}\b)(?=\s+\1)", "", input_string).strip()

    # Definiere das Muster für die Analyse
    pattern = r"(?<=\s)([A-Z]{2,3})(?=\s)\s*([^@]*)?\s*(@\s*[A-Z]+\d+)\s*(.*?)(?=\s+[A-Z]{2,3}\s|$)"

    matches = re.findall(pattern, input_string)

    results = []
    for match in matches:
        possession = match[0]
        down_and_distance = match[1].strip() if match[1] else ""
        yardline = match[2]
        details = match[3].strip()

        # Erstelle das Pydantic-Modell mit Validierung
        result = GameEvent(
            possession=possession,
            downanddistance=down_and_distance,
            yardline=yardline,
            details=details,
        )
        results.append(result.dump_model())

    return results


def parse_officials(officials_string):
    # Aufteilen des Strings in Zeilen
    lines = officials_string.strip().split("\n")

    # Initialisiere ein leeres Dictionary
    officials_dict = {}

    # Verarbeite jede Zeile
    current_title = None
    for line in lines:
        if line.endswith(":"):
            # Wenn die Zeile ein Titel ist, speichere den Titel
            current_title = line[:-1].strip()
            # Setze den Wert auf None für "Head of Statistics", wenn kein Name folgt
            if current_title == "Head of Statistics":
                officials_dict[current_title] = None
        else:
            # Andernfalls füge den Namen zum Dictionary hinzu
            officials_dict[current_title] = line.strip()

    return officials_dict


def parse_scoreboard(string: str):
    data = string.strip().split("\n")
    # Die ersten 6 Werte als Schlüssel
    headers = [item.strip() for item in data[:6]]

    # Initialisiere das Dictionary
    scoreboard = []

    # Verarbeite die Visitor-Daten
    visitor_index = 6
    visitor_team = data[visitor_index + 1].strip()
    visitor_scores = [int(data[visitor_index + i + 2].strip()) for i in range(6)]

    visitor_entry = {
        "Side": "Visitor",
        "Team": visitor_team,
        **{headers[i]: visitor_scores[i] for i in range(len(visitor_scores))},
    }
    scoreboard.append(visitor_entry)

    # Verarbeite die Home-Daten
    home_index = visitor_index + len(visitor_scores) + 2
    home_team = data[home_index + 1].strip()
    home_scores = [int(data[home_index + i + 2].strip()) for i in range(6)]

    home_entry = {
        "Side": "Home",
        "Team": home_team,
        **{headers[i]: home_scores[i] for i in range(len(home_scores))},
    }
    scoreboard.append(home_entry)

    return scoreboard


def _parse_metadata(meta_string: str, weather_string: str):
    metadata = {}

    # Extrahiere Informationen aus dem ersten String
    lines = meta_string.strip().split("\n")
    metadata["League"] = lines[0].strip()

    for line in lines[1:]:
        key_value = line.split(":", 1)
        if len(key_value) == 2:
            key = key_value[0].strip()
            value = key_value[1].strip()
            metadata[key] = value

    # Extrahiere Informationen aus dem zweiten String
    lines = weather_string.strip().split("\n")
    for line in lines:
        key_value = line.split(":", 1)
        if len(key_value) == 2:
            key = key_value[0].strip()
            value = key_value[1].strip()
            if key == "Temp":
                # Teile die Temperatur und den Wind auf
                temp_value, wind_value = value.split(", Wind:")
                metadata["Temp"] = temp_value.strip()
                metadata["Wind"] = wind_value.strip()
            else:
                metadata[key] = value

    return metadata


def extract_team_stats(string: str):
    data = string.split("\n")[8:]
    statistics = []
    stats = []
    for line in data:
        line = line.strip()

        if _is_letter_dominant(line):

            if stats:
                statistics.append(stats)
                stats = []

            stats.append(line)

        elif not _is_letter_dominant(line):

            stats.append(line)

    return statistics


def parse_team_stats(data):
    result = []

    for entry in data:
        statistic = entry[0]
        visitor = entry[1] if len(entry) > 1 else None
        home = entry[2] if len(entry) > 2 else None

        result.append(
            {
                "Statistic": statistic.lower().capitalize(),
                "Visitor": visitor,
                "Home": home,
            }
        )

    # Wenn die resultierende Liste nur einen Eintrag hat, setze Visitor und Home auf None
    if len(result) == 1:
        result[0]["Visitor"] = None
        result[0]["Home"] = None

    return result


def remove_play_by_play_summary(text: str) -> str:
    """
    Entfernt die Zeile mit "Play-by-Play Summary" und die davorstehende Zeile aus dem gegebenen Text.

    :param text: Eingabetext als String
    :return: Bereinigter Text als String
    """
    lines = text.split("\n")
    filtered_lines = []

    i = 0
    while i < len(lines):
        if i > 0 and "Play-by-Play Summary" in lines[i]:
            # Entferne die Zeile vor "Play-by-Play Summary" und die Zeile selbst
            filtered_lines.pop()
            i += 1
        else:
            filtered_lines.append(lines[i])
        i += 1

    return "\n".join(filtered_lines)


def remove_drive_header_and_footer(drive: str) -> str:
    """
    Entfernt die Header und Footer Zeilen, die den Drive zusammenfassen.

    :param text: Eingabetext als String
    :return: Bereinigter Text als String
    """
    num_lines_header = 8
    num_lines_footer = 8
    return "\n".join(drive.strip().split("\n")[num_lines_header:-num_lines_footer])


def parse_football_plays(text: str):
    """
    Parst einen Text in eine Liste von Abschnitten basierend auf dem Muster:
    - Zwei Großbuchstaben, dann neue Zeile
    - Ein String mit "&", dann neue Zeile
    - Ein String mit "@" beginnend, dann neue Zeile
    - Ein String, solange bis wieder eine neue Zeile mit zwei Großbuchstaben kommt

    :param text: Der Eingabetext als String
    :return: Liste von extrahierten Abschnitten
    """
    pattern = re.compile(
        r"""
        ([A-Z]{2})\n         # Zwei Großbuchstaben gefolgt von einer neuen Zeile
        (.+?&)\n          # Ein beliebiger String mit '&', dann neue Zeile
        (@.+?)\n        # Ein String, der mit '@' beginnt, dann neue Zeile
        ((?:.+\n)+?)  # Mehrere Zeilen bis zur nächsten Übereinstimmung
        (?=[A-Z]{2}\n|$)  # Stopp bei zwei Großbuchstaben oder Ende des Textes
    """,
        re.VERBOSE,
    )

    matches = pattern.findall(text)

    result = ["\n".join(match) for match in matches]
    return result


def process_game_log(log_list):
    processed = []
    temp_group = {}
    pattern = re.compile(r"^\d+&\d+$")  # Muster für Down & Distance (z. B. 1&10)
    team_pattern = re.compile(
        r"^\s*([A-Z]{2})$"
    )  # Erkennung von zweistelligen Team-Codes mit optionalem Leerzeichen davor

    i = 0
    while i < len(log_list):
        entry = log_list[i].strip()  # Leerzeichen entfernen

        # Falls die Gruppe leer ist, starte sie mit einem 2-stelligen Team-Code
        if not temp_group and team_pattern.match(entry):
            temp_group["Index"] = team_pattern.match(entry).group(1)
            i += 1
            continue

        # Falls Down & Distance fehlt, aber @ kommt direkt nach Team, füge Dummy ein
        if "Down&Distance" not in temp_group and entry.startswith("@"):
            temp_group["Down&Distance"] = "0&0"

        # Down & Distance erkennen
        if pattern.match(entry) and "Down&Distance" not in temp_group:
            temp_group["Down&Distance"] = entry

        # Yardline mit @ erkennen
        elif entry.startswith("@") and "Yard Line" not in temp_group:
            temp_group["YardLine"] = entry

        # Falls Spielbeschreibung kommt (oder weitere aneinanderhängende), hinzufügen
        elif "Details" in temp_group or len(temp_group) >= 3:
            clean_entry = re.sub(
                r"\s+[A-Z]{2}$", "", entry
            )  # Entferne nachgestellte Team-Kürzel
            temp_group["Details"] = (
                temp_group.get("Details", "") + " " + clean_entry
                if "Details" in temp_group
                else clean_entry
            )

            # Prüfen, ob nächster Eintrag auch eine Spielbeschreibung ist
            if (
                i + 1 < len(log_list)
                and not log_list[i + 1].startswith("@")
                and not pattern.match(log_list[i + 1])
                and not team_pattern.match(log_list[i + 1])
            ):
                i += 1  # Überspringen, weil zusammengehörig
                temp_group["Details"] += " " + log_list[i].strip()

        # Falls die Gruppe vollständig ist, speichern und zurücksetzen
        if len(temp_group) >= 4:
            processed.append(temp_group)
            temp_group = {}

        i += 1

    return processed


def parse_drives(drive: str) -> list:
    drive = remove_play_by_play_summary(drive)
    drive = remove_drive_header_and_footer(drive)

    game_logs = process_game_log(drive.split("\n"))
    return game_logs


def parse_table_data(
    string: str, no_columns: int, keys: list | None = None, offset: int | None = None
):
    """
    Parses a string containing tabular data into a list of dictionaries.

    Parameters
    ----------
    data : str
        The input string containing tabular data, with values separated by newlines.
    num_columns : int
        The number of columns in the table.
    keys : list of str, optional
        A list of column headers to use as dictionary keys. If None, the first `offset` rows are used.
    offset : int, optional
        The number of initial rows to use as keys. Defaults to `num_columns` if not provided.

    Returns
    -------
    list of dict
        A list of dictionaries representing the parsed table data, where each dictionary corresponds to a row.
    """
    data = ("Index\n" + string.strip()).split("\n")
    logger.info(data)
    if offset is None:
        offset = no_columns

    if keys is None:
        keys = data[:offset]

    values = data[offset:]

    records = []
    current_record = {}

    for index, value in enumerate(values):
        pointer = index % no_columns
        current_record[str(keys[pointer])] = value

        if pointer == no_columns - 1:
            records.append(current_record)
            current_record = {}
    return records


#######################################################
#########                PAGES                #########
#######################################################


def parse_page_one(page_one: str, doc: dict) -> dict:
    meta, rest = page_one.split("Score by Quarters")
    score_quarters, rest = rest.split("Scoring Plays")
    scoring_plays, rest = rest.split("Field\nGoals")
    field_goals, rest = rest.split("Officials")
    officials, weather = rest.split("Weather\n")

    doc["meta"] = _parse_metadata(meta, weather)
    doc["score_board"] = parse_scoreboard(score_quarters)
    doc["officials"] = parse_officials(officials)
    doc["touchdowns"] = parse_table_data(scoring_plays.split("Team")[1], 6)
    doc["field_goals"] = parse_table_data(field_goals.split("Team")[1], 6)
    return doc


def parse_page_two(page_two: str, doc: dict) -> dict:
    team_stats = extract_team_stats(page_two)
    doc["team_stats"] = parse_team_stats(team_stats)
    return doc


def parse_page_three(page_three: str, doc: dict) -> dict:
    _, passing_visitors, rest = page_three.split("Passing")
    passing_home, rushing_visitors, rest = rest.split("Rushing")
    rushing_home, receiving_visitors, receiving_home = rest.split("Receiving")

    doc["individual_stats"] = {
        "passing": {},
        "rushing": {},
        "receiving": {},
    }

    doc["individual_stats"]["passing"]["visitors"] = parse_table_data(
        passing_visitors, 10
    )
    doc["individual_stats"]["passing"]["home"] = parse_table_data(passing_home, 10)

    doc["individual_stats"]["rushing"]["visitors"] = parse_table_data(
        rushing_visitors, 6
    )
    doc["individual_stats"]["rushing"]["home"] = parse_table_data(rushing_home, 6)

    doc["individual_stats"]["receiving"]["visitors"] = parse_table_data(
        receiving_visitors, 6
    )
    doc["individual_stats"]["receiving"]["home"] = parse_table_data(receiving_home, 6)
    return doc


def parse_page_four(page_four: str, doc: dict) -> dict:
    _, visitors, home = page_four.split("Defense")

    doc["defense_stats"] = {"visitors": {}, "home": {}}
    doc["defense_stats"]["visitors"] = parse_table_data(visitors, 13)
    doc["defense_stats"]["home"] = parse_table_data(home, 13)
    return doc


def parse_page_five(page_five: str, doc: dict) -> dict:
    _, home, visitors = page_five.split("How Given")
    keys = [
        "index",
        "Start QTR",
        "Start Time",
        "End QTR",
        "End Time",
        "Poss. Time",
        "How Obtained",
        "Start Yrd",
        "No. Plays",
        "Net Yds",
        "End Yrd",
        "How Given Up",
    ]

    doc["drives"] = {"visitors": {}, "home": {}}
    doc["drives"]["visitors"] = parse_table_data(
        string=visitors, no_columns=12, offset=11, keys=keys
    )
    doc["drives"]["home"] = parse_table_data(
        string=home, no_columns=12, offset=11, keys=keys
    )

    return doc

def extract_pattern(input_string, pattern):
    matches = re.findall(pattern, input_string, re.MULTILINE)
    return matches

def merge_lists(list1, list2):
    merged = []
    for item1, item2 in zip(list1, list2):
        merged.append(f"{item1.strip()} {item2.strip()}")
    return merged

def extract_entries(text, drive_no, quarter): #TODO: Zeilen in das entsprechende Format bringen
    pattern_drive_summary = r'\s*Plays\s+\d+\s+Yards\s+-?\d+\s+TOP\s+\d{2}:\d{2}\s+SCORE\s*[\d-]*'
    pattern = rf"(?<=\s)([A-Z]{{2,3}})(?=\s)\s*([^@]*)?\s*(@\s*[A-Z]+\d+)\s*(.*?)(?=\s+[A-Z]{{2,3}}\s|$|(?=.{0,29}$)|(?={pattern_drive_summary}))"
    
    entries = []
    
    for match in re.finditer(pattern, text, re.DOTALL):
        entry = {
            'Quarter': quarter, 
            'Series': drive_no,
            'Index': match.group(1),
            'Down&Distance': match.group(2).strip() if match.group(2) else '',
            'YardLine': match.group(3),
            'Details': match.group(4).strip().replace('\n', ' ')
        }
        entries.append(entry)

    return entries

def extract_number(text):
    pattern = r'\((\d+)\s+Quarter\)'
    match = re.search(pattern, text)
    
    if match:
        return match.group(1)  # Gibt die gefundene Zahl zurück
    return None  # Gibt None zurück, wenn kein Match gefunden wurde

def parse_last_pages(pages: str, doc: dict) -> dict:
    last_sections = "\n".join(pages).split("Participation Report")
    participation_report_is_in = len(last_sections) == 3

    if participation_report_is_in:
        doc["participation"] = {"visitors": {}, "home": {}}

        drives, home_pr, visitors_pr = last_sections

        adj_home_pr_starter_string = "Last Name\nPosition\n#" + (home_pr.split("#")[1])
        adj_home_pr_bench_string = "Last Name\nPosition\n#" + (home_pr.split("#")[2])

        doc["participation"]["home"]["starter"] = parse_table_data(
            adj_home_pr_starter_string, 4
        )
        doc["participation"]["home"]["bench"] = parse_table_data(
            adj_home_pr_bench_string, 4
        )

        adj_visitors_pr_starter_string = "Last Name\nPosition\n#" + (
            visitors_pr.split("#")[1]
        )
        adj_visitors_pr_bench_string = "Last Name\nPosition\n#" + (
            visitors_pr.split("#")[2]
        )
        doc["participation"]["visitors"]["starter"] = parse_table_data(
            adj_visitors_pr_starter_string, 4
        )
        doc["participation"]["visitors"]["bench"] = parse_table_data(
            adj_visitors_pr_bench_string, 4
        )
    else:
        drives = last_sections[0]

    quarter_list = drives.split("Play-by-Play Summary")
    doc["drives"] = {}
    drive_starts = []
    drive_summary = []
    for quarter_no, quarter_str in enumerate(quarter_list[1:], start=1): 
        pattern_drive_start = r'^[A-Za-z\s]+(Spot:\s+\w+\s+Clock:\s+\d{2}:\d{2}\s+Drive:\s+\d+)\s*'  
        pattern_split_drive_start = r'Spot:\s+\w+\s+Clock:\s+\d{2}:\d{2}\s+Drive:\s+'
        pattern_drive_summary = r'\s*Plays\s+\d+\s+Yards\s+-?\d+\s+TOP\s+\d{2}:\d{2}\s+SCORE\s*[\d-]*'
        drive_list = re.split(pattern_split_drive_start, quarter_str)
        for drive in drive_list:
            drive_no = drive[:2].strip() # TODO: Fehler bei Quarterwechsel (1 auf 2, 3 auf 4) 
            print(f'Drive: {drive_no}'.center(79, "-"))
            print(extract_entries(drive, quarter=quarter_no, drive_no=drive_no))

        matches_start = extract_pattern(quarter_str, pattern_drive_start)
        matches_summary = extract_pattern(quarter_str, pattern_drive_summary)
        drive_starts.extend(matches_start)
        drive_summary.extend(matches_summary)

        drive_list = quarter_str.split("Drive Start")
        for quarter_no, drive in enumerate(drive_list):
            logger.info(f"{quarter_no = }")
            drive_str = " ".join(drive.split("\n"))
            drive_str = remove_drive_summary(remove_drive_start_info(drive_str))
            doc["drives"][f"Drive {str(quarter_no).zfill(2)}"] = parse_from_str_to_drive(drive_str)

    merged_drives = merge_lists(drive_starts, drive_summary)
    print(merged_drives)
    
    return doc


def main():
    pages = extract_text_from_pdf(PATH_PDF)

    doc = {}

    parsers = [
        parse_page_one,
        parse_page_two,
        parse_page_three,
        parse_page_four,
        parse_page_five,
    ]

    # Parse the first five pages using corresponding functions
    for i, parser in enumerate(parsers):
        doc = parser(pages[i], doc)

    # Parse the remaining pages
    doc = parse_last_pages(pages[5:], doc)

    save_dict_to_json(doc, PATH_JSON)


# Program
if __name__ == "__main__":
    main()
