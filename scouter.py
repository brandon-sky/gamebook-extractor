# Dependencies
from datetime import datetime, timedelta
import functools
import json

import PyPDF2
from rich import print

# Const. Vars
TEST_HEADER = "European League of Football - Game Report"
PATH_PDF = "data/raw/stats_ssms2404.pdf"
PATH_JSON = "data/interim/stats_ssms2404.json"
CALL_COUNTS = {}


# Funcs
def log_function_name(func):
    """Decorator, der den Namen der aufgerufenen Funktion ausgibt und die Aufrufanzahl zählt."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        CALL_COUNTS[func.__name__] = CALL_COUNTS.get(func.__name__, 0) + 1
        # print(f"Aufruf der Funktion: {func.__name__} (Aufrufe: {CALL_COUNTS[func.__name__]})")
        return func(*args, **kwargs)

    return wrapper


@log_function_name
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text_per_page = []
        for page in reader.pages:
            text_per_page.append(page.extract_text())
    return text_per_page


@log_function_name
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


@log_function_name
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


@log_function_name
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


@log_function_name
def is_statistic_line(line):
    # Zähle die Buchstaben, Zahlen und Sonderzeichen
    letters = sum(c.isalpha() for c in line)
    digits = sum(c.isdigit() for c in line)
    special_chars = sum(not c.isalnum() for c in line)

    # Überprüfe, ob es mehr Buchstaben als Zahlen oder Sonderzeichen gibt
    return letters > digits + special_chars


@log_function_name
def extract_statistics(string: str):
    data = string.split("\n")[8:]
    statistics = []
    stats = []
    for line in data:
        line = line.strip()

        if is_statistic_line(line):

            if stats:
                statistics.append(stats)
                stats = []

            stats.append(line)

        elif not is_statistic_line(line):

            stats.append(line)

    return statistics


@log_function_name
def convert_to_dicts(data):
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


@log_function_name
def create_dicts_from_list(
    string: str, no_columns: int, keys: list | None = None, offset: int | None = None
):
    data = ("Index\n" + string.strip()).split("\n")

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


@log_function_name
def extract_drives(drive: str) -> list:
    clean_drive = "\n".join(drive.strip().split("\n")[8:-8])
    header = "Down&Distance\nYardLine\nDetails\n"
    return create_dicts_from_list(header + clean_drive, 4)


@log_function_name
def parse_page_one(page_one: str, doc: dict) -> dict:
    meta, rest = page_one.split("Score by Quarters")
    score_quarters, rest = rest.split("Scoring Plays")
    scoring_plays, rest = rest.split("Field\nGoals")
    field_goals, rest = rest.split("Officials")
    officials, weather = rest.split("Weather\n")

    doc["meta"] = _parse_metadata(meta, weather)
    doc["score_board"] = parse_scoreboard(score_quarters)
    doc["officials"] = parse_officials(officials)
    doc["touchdowns"] = create_dicts_from_list(scoring_plays.split("Team")[1], 6)
    doc["field_goals"] = create_dicts_from_list(field_goals.split("Team")[1], 6)
    return doc


@log_function_name
def parse_page_two(page_two: str, doc: dict) -> dict:
    temp = extract_statistics(page_two)
    doc["team_stats"] = convert_to_dicts(temp)
    return doc


@log_function_name
def parse_page_three(page_three: str, doc: dict) -> dict:
    _, passing_visitors, rest = page_three.split("Passing")
    passing_home, rushing_visitors, rest = rest.split("Rushing")
    rushing_home, receiving_visitors, receiving_home = rest.split("Receiving")

    doc["individual_stats"] = {
        "passing": {},
        "rushing": {},
        "receiving": {},
    }

    doc["individual_stats"]["passing"]["visitors"] = create_dicts_from_list(
        passing_visitors, 10
    )
    doc["individual_stats"]["passing"]["home"] = create_dicts_from_list(
        passing_home, 10
    )

    doc["individual_stats"]["rushing"]["visitors"] = create_dicts_from_list(
        rushing_visitors, 6
    )
    doc["individual_stats"]["rushing"]["home"] = create_dicts_from_list(rushing_home, 6)

    doc["individual_stats"]["receiving"]["visitors"] = create_dicts_from_list(
        receiving_visitors, 6
    )
    doc["individual_stats"]["receiving"]["home"] = create_dicts_from_list(
        receiving_home, 6
    )
    return doc


@log_function_name
def parse_page_four(page_four: str, doc: dict) -> dict:
    _, visitors, home = page_four.split("Defense")

    doc["defense_stats"] = {"visitors": {}, "home": {}}
    doc["defense_stats"]["visitors"] = create_dicts_from_list(visitors, 13)
    doc["defense_stats"]["home"] = create_dicts_from_list(home, 13)
    return doc


@log_function_name
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
    doc["drives"]["visitors"] = create_dicts_from_list(
        string=visitors, no_columns=12, offset=11, keys=keys
    )
    doc["drives"]["home"] = create_dicts_from_list(
        string=home, no_columns=12, offset=11, keys=keys
    )

    return doc


@log_function_name
def parse_last_pages(pages: str, doc: dict) -> dict:
    last_sections = "\n".join(pages).split("Participation Report")
    participation_report_is_in = len(last_sections) == 3

    if participation_report_is_in:
        doc["participation"] = {"visitors": {}, "home": {}}

        drives, home_pr, visitors_pr = last_sections

        adj_home_pr_starter_string = "Last Name\nPosition\n#" + (home_pr.split("#")[1])
        adj_home_pr_bench_string = "Last Name\nPosition\n#" + (home_pr.split("#")[2])

        doc["participation"]["home"]["starter"] = create_dicts_from_list(
            adj_home_pr_starter_string, 4
        )
        doc["participation"]["home"]["bench"] = create_dicts_from_list(
            adj_home_pr_bench_string, 4
        )

        adj_visitors_pr_starter_string = "Last Name\nPosition\n#" + (
            visitors_pr.split("#")[1]
        )
        adj_visitors_pr_bench_string = "Last Name\nPosition\n#" + (
            visitors_pr.split("#")[2]
        )
        doc["participation"]["visitors"]["starter"] = create_dicts_from_list(
            adj_visitors_pr_starter_string, 4
        )
        doc["participation"]["visitors"]["bench"] = create_dicts_from_list(
            adj_visitors_pr_bench_string, 4
        )
    else:
        drives = last_sections[0]

    drive_list = drives.split("Drive Start")

    doc["drives"] = {}

    for index, drive in enumerate(drive_list[1:], start=1):
        doc["drives"][f"Drive {str(index).zfill(2)}"] = extract_drives(drive)

    return doc


@log_function_name
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


def main():
    pages = extract_text_from_pdf(PATH_PDF)

    page_one = pages[0]
    page_two = pages[1]
    page_three = pages[2]
    page_four = pages[3]
    page_five = pages[4]
    pages = pages[5:]

    doc = dict()

    # Page 1
    doc = parse_page_one(page_one, doc)

    # Page 2
    doc = parse_page_two(page_two, doc)

    # Page 3
    doc = parse_page_three(page_three, doc)

    # Page 4
    doc = parse_page_four(page_four, doc)

    # Page 5
    doc = parse_page_five(page_five, doc)

    # Page 6 and following
    doc = parse_last_pages(pages, doc)

    # save_dict_to_json(doc, PATH_JSON)
    # print(doc)
    print(CALL_COUNTS)


# Program
if __name__ == "__main__":
    main()
