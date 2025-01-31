# Dependencies
from datetime import datetime, timedelta
import functools
import json

import PyPDF2
from rich import print

# Const. Vars
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


def parse_drives(drive: str) -> list:
    clean_drive = "\n".join(drive.strip().split("\n")[8:-8])
    header = "Down&Distance\nYardLine\nDetails\n"
    return parse_table_data(header + clean_drive, 4)


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

    drive_list = drives.split("Drive Start")

    doc["drives"] = {}

    for index, drive in enumerate(drive_list[1:], start=1):
        doc["drives"][f"Drive {str(index).zfill(2)}"] = parse_drives(drive)

    return doc


def main():
    pages = extract_text_from_pdf(PATH_PDF)
    
    doc = {}
    
    parsers = [
        parse_page_one,
        parse_page_two,
        parse_page_three,
        parse_page_four,
        parse_page_five
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
