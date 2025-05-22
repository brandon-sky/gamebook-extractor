# Dependencies
import re

import PyPDF2
import numpy as np
import streamlit as st
import pandas as pd

from catalog.teams import NAMES
from scouter import (
    parse_page_one,
    parse_page_two,
    parse_page_three,
    parse_page_four,
    parse_page_five,
    parse_last_pages,
)

# Const
PARSERS = [
    parse_page_one,
    parse_page_two,
    parse_page_three,
    parse_page_four,
    parse_page_five,
]

# Column names
COLUMN_PLAY_TYPE = "PLAY TYPE"
COLUMN_POSSESION = "POSS"
COLUMN_PENALTY = "PENALTY"
COLUMN_PENALTY_OD = "PEN O/D"
COLUMN_RESULT = "RESULT"


# Func
def extract_text_from_pdf(uploaded_file):
    if uploaded_file is not None:
        reader = PyPDF2.PdfReader(uploaded_file)
        text_per_page = [page.extract_text() for page in reader.pages]
        return text_per_page
    return None


def dict_to_dataframe(data: dict) -> pd.DataFrame:
    """
    Konvertiert ein Dictionary mit Drive-Daten in ein Pandas DataFrame.

    :param data: Dictionary mit Drive-Daten
    :return: Pandas DataFrame mit allen Plays und einer Drive-Spalte
    """
    records = []

    # Daten extrahieren und aufbereiten
    for drive, plays in data.items():
        for play in plays:
            play["Drive"] = int(
                drive.split()[1]
            )  # Drive als zusätzliche Spalte hinzufügen
            records.append(play)

    # DataFrame erstellen
    df = pd.DataFrame(records)

    # Spaltennamen und Werte bereinigen
    df.columns = df.columns.str.strip()
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    # Spalte "Drive" an den Anfang setzen
    df = df[["Drive"] + [col for col in df.columns if col != "Drive"]]
    df.rename(columns={"Drive": "SERIES"}, inplace=True)
    return df


def split_down_distance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Spaltet die Spalte "Down&Distance" in separate Spalten "Down" und "Distance" und entfernt die ursprüngliche Spalte.

    :param df: Pandas DataFrame mit einer Spalte "Down&Distance"
    :return: DataFrame mit zusätzlichen Spalten "Down" und "Distance" ohne "Down&Distance"
    """
    df[["DN", "DIST"]] = df["Down&Distance"].str.split("&", expand=True)
    df.drop(columns=["Down&Distance"], inplace=True)
    return df


def transform_yardline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transformiert die Spalte "YardLine", indem es das "@" entfernt und das Vorzeichen anhand des Index anpasst.

    Falls die YardLine den gleichen Code wie der Index enthält (z. B. "@ RF44" für Index "RF"), wird der Wert negativ.
    Falls sie unterschiedlich sind, bleibt er positiv.

    :param df: Pandas DataFrame mit einer Spalte "YardLine" und "Index"
    :return: DataFrame mit transformierter "YardLine"
    """

    def convert_yardline(row):
        if isinstance(row["YardLine"], str) and "@" in row["YardLine"]:
            parts = row["YardLine"].split()
            if len(parts) == 2 and row["Index"].strip() == parts[1][:2]:
                return -1 * int(parts[1][2:])
            return int(parts[1][2:])
        return row["YardLine"]

    df["YardLine"] = df.apply(convert_yardline, axis=1)
    df.rename(columns={"YardLine": "YARD LN"}, inplace=True)
    return df


def transform_down_distance_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ersetzt leere Felder und "" in den angegebenen Spalten mit 0.

    :param df: Pandas DataFrame
    :param columns_to_replace: Liste der Spalten, in denen die Werte ersetzt werden sollen
    :return: DataFrame mit ersetzten Werten in den angegebenen Spalten
    """

    columns_to_replace = ["DN", "DIST"]

    # Leere Felder und "" in den ausgewählten Spalten durch 0 ersetzen
    df[columns_to_replace] = df[columns_to_replace].fillna(0)
    df[columns_to_replace] = df[columns_to_replace].replace("", 0)

    return df


def rename_and_reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Umbenennung der Spalte "Index" in "Possession" und Neuanordnung der Spalten in der gewünschten Reihenfolge.

    :param df: Pandas DataFrame mit den ursprünglichen Spalten
    :return: DataFrame mit umbenannten und neu geordneten Spalten
    """
    df.rename(columns={"Index": COLUMN_POSSESION, "Quarter": "QTR"}, inplace=True)
    column_order = [
        "QTR",
        "SERIES",
        "YARD LN",
        "DN",
        "DIST",
        COLUMN_POSSESION,
        "Details",
    ]
    df = df[column_order]
    return df


def add_play_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine Spalte "PLAY #" zu einem DataFrame hinzu, die mit 1 beginnt und mit jeder Zeile hochgezählt wird.

    Parameters
    ----------
    df : pandas.DataFrame
        Das Eingabe-DataFrame, dem die neue Spalte hinzugefügt werden soll.

    Returns
    -------
    pandas.DataFrame
        Ein neues DataFrame mit der hinzugefügten Spalte "PLAY #".
    """
    df_copy = df.copy()  # Erstelle eine Kopie des DataFrames
    df_copy.insert(0, "PLAY #", range(1, len(df_copy) + 1))
    return df_copy


def add_play_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Play Type" hinzu, die basierend auf dem Inhalt der "Details"-Spalte den Spielzugtyp bestimmt.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "Play Type"-Spalte
    """

    def categorize_play(details):
        details_lower = details.lower()
        if "rush" in details_lower:
            return "Run"
        elif "pass" in details_lower or "sacked" in details_lower:
            return "Pass"
        elif "field goal" in details_lower:
            return "FG"
        elif "punt" in details_lower:
            return "Punt"
        elif "timeout" in details_lower:
            return None
        elif "knee" in details_lower:
            return "Run"
        elif "kickoff" in details_lower:
            return "KO"
        elif "extra point" in details_lower:
            return "Extra Pt."
        return None

    df[COLUMN_PLAY_TYPE] = df["Details"].apply(categorize_play)
    return df


def add_result_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Result" hinzu, die den Ausgang des Spielzugs basierend auf der "Details"-Spalte kategorisiert.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "Result"-Spalte
    """

    def categorize_result(details):
        details_lower = details.lower()
        if "no-play" in details_lower:
            return "Penalty"  # TODO: write function to add row
        elif "safety" in details_lower:
            return "Safety"  # TODO: Changed from Penalty (Pending) to "Safety" because of +2
        # elif "penalty" in details_lower:
        #     return "Penalty (Pending)"
        elif "rush" in details_lower or "knee" in details_lower:
            if "fumbles" in details_lower:
                return "Fumble"  # TODO: check if possesion changed
            elif "touchdown" in details_lower:
                return "Rush, TD"
            elif "two-point-conversion" in details_lower:
                return "Rush, TPC"  # TODO: added two-point-conversion as TPC check
            return "Rush"
        elif "incomplete" in details_lower:
            return "Incomplete"
        elif "complete" in details_lower:
            if "fumbles" in details_lower:
                return "Complete, Fumble"  # TODO: check if possesion changed
            elif "touchdown" in details_lower:
                return "Complete, TD"
            elif "two-point-conversion" in details_lower:
                return "Complete, TPC"  # TODO: added two-point-conversion as TPC check
            return "Complete"
        elif "sacked" in details_lower:
            if "fumbles" in details_lower:
                return "Sack, Fumble"  # TODO: check if possesion changed
            return "Sack"
        elif "intercepted" in details_lower:
            if "touchdown" in details_lower:
                return "Interception, TD"
            return "Interception"
        elif "succeeds" in details_lower:
            return "Good"
        elif "is good" in details_lower:
            return "Good"
        elif "misses" in details_lower:
            return "No good"
        elif "no good" in details_lower:
            return "No good"
        elif "returned" in details_lower:
            return "Return"
        elif "fair catch" in details_lower:
            return "Fair Catch"
        elif "timeout" in details_lower:
            return "Timeout"
        elif "end of game" in details_lower:
            return "COP"
        elif "out-of-bounds" in details_lower:
            return "Out of Bounds"
        elif "touchback" in details_lower:
            return "Touchback"  # TODO: touchback/major touchback
        elif "downed" in details_lower:
            return "Downed"
        return "Other"

    df[COLUMN_RESULT] = df["Details"].apply(categorize_result)
    return df


def verify_fumble(df: pd.DataFrame) -> pd.DataFrame:
    """
    Überprüft die "RESULT"-Spalte eines DataFrames auf den Begriff "Fumble"
    und passt den Wert basierend auf der "POSS"-Spalte an.

    Wenn "Fumble" in der "RESULT"-Spalte gefunden wird, wird überprüft,
    ob sich der Wert in der "POSS"-Spalte im Vergleich zur nächsten Zeile ändert.
    Wenn sich der Wert nicht ändert, wird "Fumble" durch einen entsprechenden
    Wert ersetzt (entweder 'Sack', 'Complete' oder 'Rush').

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame mit den Spalten "RESULT" und "POSS".

    Returns
    -------
    pd.DataFrame
        Der modifizierte DataFrame mit aktualisierten Werten in der "RESULT"-Spalte.
    """
    for index, row in df.iterrows():
        current_result = row["RESULT"].lower()
        if "fumble" in current_result:
            current_poss = row["POSS"]
            next_poss = df["POSS"].shift(-1).iloc[index]
            print(f"{current_poss = }")
            print(f"{next_poss = }")
            if current_poss == next_poss:
                if "sack" in current_result:
                    new_result = "Sack"
                elif "complete" in current_result:
                    new_result = "Complete"
                else:
                    new_result = "Rush"
                df.at[index, "RESULT"] = new_result
    return df


def add_kicking_yards_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "KickingYards" hinzu, die die Kicking Yards extrahiert.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "KickingYards"-Spalte
    """

    def extract_kicking_yards(details):
        """
        Extrahiert die Kicking Yards aus der "Details"-Spalte.

        :param details: String aus der "Details"-Spalte
        :return: Integer-Wert der Yards oder None
        """
        match = re.search(r"kickoff for (\d+) yards", details)
        return int(match.group(1)) if match else None

    df["KICK YARDS"] = df["Details"].apply(
        extract_kicking_yards
    )  # TODO: consider PAT too
    return df


def add_caught_on_column(
    df: pd.DataFrame,
) -> pd.DataFrame:  # TODO: consider Fumble Recovery too
    """
    Fügt eine neue Spalte "CaughtOn" hinzu, berechnet mit der Formel:
    100 + YARD LN - KICK YARDS

    :param df: Pandas DataFrame mit den Spalten "YARD LN" und "KICK YARDS"
    :return: DataFrame mit der neuen "CaughtOn"-Spalte
    """

    result = (100 + df["YARD LN"] - df["KICK YARDS"]) * -1
    df["CAUGHT ON"] = result.where(result != 0, np.nan)
    return df


def fill_in_caught_on_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrahiert das Muster 'V4', 'R23' usw. nach 'recovered at' aus der Spalte 'Details'
    und fügt den entsprechenden Wert in die Spalte 'CAUGHT ON' ein,
    abhängig vom Vergleich des Anfangsbuchstabens mit der Spalte 'POSS'.
    Bestehende Werte in 'CAUGHT ON' werden nicht überschrieben.

    Parameters
    ----------
    df : pandas.DataFrame
        Das Eingabe-DataFrame, das die Spalten 'Details', 'POSS' und 'CAUGHT ON' enthält.

    Returns
    -------
    pandas.DataFrame
        Ein neues DataFrame mit aktualisierter Spalte 'CAUGHT ON'.
    """

    def extract_recovered(text):
        match = re.search(r"recovered at (\b[A-Z]\d+\b)", text)
        return match.group(1) if match else None

    df_copy = df.copy()  # Erstelle eine Kopie des DataFrames
    df_copy["CAUGHT ON2"] = df_copy["Details"].apply(extract_recovered).fillna("")

    def calculate_caught_on(row):
        caught_on_value = row["CAUGHT ON2"]
        poss_value = row["POSS"]

        if caught_on_value and poss_value:
            letter_match = caught_on_value[0]
            number_value = int(caught_on_value[1:]) if len(caught_on_value) > 1 else 0

            if letter_match == poss_value[0]:
                return -number_value
            else:
                return number_value
        return row[
            "CAUGHT ON"
        ]  # Behalte bestehenden Wert, wenn kein neuer Wert vorhanden ist

    df_copy["CAUGHT ON"] = df_copy.apply(calculate_caught_on, axis=1)

    return df_copy


def add_return_yards_column(
    df: pd.DataFrame,
) -> pd.DataFrame:  # TODO: consider Fumble Recovery too
    """
    Fügt eine neue Spalte "RetYards" hinzu, berechnet als:
    YARD LN der nächsten Zeile - CaughtOn der aktuellen Zeile.

    :param df: Pandas DataFrame mit den Spalten "YARD LN" und "CaughtOn"
    :return: DataFrame mit der neuen "RetYards"-Spalte
    """

    # Verschiebe "YARD LN" nach oben (entspricht YARD LN der nächsten Spielzug)
    next_yard_ln = df["YARD LN"].shift(-1)

    # Berechne Return Yards
    df["RET YARDS"] = (next_yard_ln - df["CAUGHT ON"]) * (-1)

    return df


def add_penalty_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt zwei neue Spalten hinzu:
    - 'Penalty O/D': Das Team, das die Strafe erhalten hat (steht direkt vor 'penalty:').
    - 'Penalty': Die Art des Vergehens, z. B. 'DPI Defensive Pass Interference'.

    Die Spalten werden nur für Zeilen gesetzt, in denen entweder 'no-play' in 'Details' steht
    oder 'DN' None ist. Sonst bleiben sie leer.
    """

    def extract_penalty_team(details):
        if not isinstance(details, str):
            return None
        match = re.search(
            r"((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+penalty)", details
        )
        if match:
            return match.group(1).strip()  # Entferne überflüssige Leerzeichen
        return None

    def extract_penalty_type(details):
        if not isinstance(details, str):
            return None
        match = re.search(r"penalty[\W_]*(?=[A-Z]+)([A-Z]+)", details)
        return match.group(1) if match else None

    df = df.copy()
    mask = (
        df["Details"].str.contains("no-play", case=False, na=False) | df["DN"].isnull()
    )
    df[COLUMN_PENALTY_OD] = None
    df[COLUMN_PENALTY] = None
    df.loc[mask, COLUMN_PENALTY_OD] = df.loc[mask, "Details"].apply(
        extract_penalty_team
    )
    df.loc[mask, COLUMN_PENALTY] = df.loc[mask, "Details"].apply(extract_penalty_type)
    return df


def split_penalty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Wenn 'Result' == 'Penalty (Pending)' oder 'Penalty', wird eine neue Zeile
    direkt darunter eingefügt, welche die Informationen aus 'Penalty O/D' und 'Penalty'
    übernimmt. Bei 'Penalty (Pending)' werden diese Werte in der Originalzeile geleert.
    """
    new_rows = []

    for idx, row in df.iterrows():
        # Ursprüngliche Zeile hinzufügen
        new_rows.append(row.copy())

        # Bedingung prüfen
        if "penalty:" in row["Details"].lower():
            penalty_row = row.copy()
            # penalty_row['ODK'] = row['ODK']  # ggf. anpassen, falls ODK für Einordnung gebraucht wird
            penalty_row[COLUMN_RESULT] = "Penalty"  # Neue Markierung
            # penalty_row['ODK'] = 'S'
            penalty_row["Series"] = None
            penalty_row["YARD LN"] = None
            penalty_row["DN"] = None
            penalty_row["DIST"] = None

            # # Wenn "Penalty (Pending)", dann original leeren
            # if "no-play" not in row['Details'].lower():
            #     new_rows[-1][COLUMN_PENALTY_OD] = None
            #     new_rows[-1][COLUMN_PENALTY] = None

            new_rows.append(penalty_row)

    # Neuer DataFrame mit reset_index
    new_df = pd.DataFrame(new_rows).reset_index(drop=True)
    return new_df


def add_passer_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Passer" hinzu, die den Namen des Passgebers extrahiert.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "Passer"-Spalte
    """

    def extract_passer(details):
        match = re.search(r"([A-Z]\.?\s[A-Z][a-z]+)\s(?:pass|gets sacked)", details)
        return match.group(1) if match else None

    df["Passer"] = df["Details"].apply(extract_passer)
    return df


def add_rusher_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Rusher" hinzu, die den Namen des Ballträgers extrahiert.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "Rusher"-Spalte
    """

    def extract_rusher(details):
        match = re.search(r"([A-Z]\.?\s[A-Z][a-z]+)\s(?:rush)", details)
        return match.group(1) if match else None

    df["Rusher"] = df["Details"].apply(extract_rusher)
    return df


def add_receiver_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Receiver" hinzu, die den Namen des Passempfängers extrahiert.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "Receiver"-Spalte
    """

    def extract_receiver(details):
        """
        Extrahiert den Namen des Receivers aus der "Details"-Spalte, wenn "complete to" vorkommt.

        :param details: String aus der "Details"-Spalte
        :return: Name des Receivers oder None
        """
        match = re.search(r"complete to ([A-Z]\.?\s[A-Z][a-z]+)\sfor", details)
        return match.group(1) if match else None

    df["Receiver"] = df["Details"].apply(extract_receiver)
    return df


def add_tackler_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Tackler" hinzu, die den Namen des Tacklers extrahiert.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "Tackler"-Spalte
    """

    def extract_tackler(details):
        """
        Extrahiert den Namen des Tacklers aus der "Details"-Spalte, wenn "tackled by" vorkommt.

        :param details: String aus der "Details"-Spalte
        :return: Name des Tacklers oder None
        """
        match = re.search(r"tackled by ([A-Z]\.?\s[A-Z][a-z]+)", details)
        return match.group(1) if match else None

    df["Tackler"] = df["Details"].apply(extract_tackler)
    return df


def add_kicker_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Kicker" hinzu, die den Namen des Kickers aus der "Details"-Spalte extrahiert.

    Mögliche Phrasen:
    - "<Initial>. <Nachname> attempts an extra point..."
    - "<Initial>. <Nachname> attempts a <xx> yards field goal..."
    - "<Initial>. <Nachname> kickoff for <xx> yards..."

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit neuer Spalte "Kicker"
    """

    def extract_kicker_or_punter(details):
        if not isinstance(details, str):
            return None

        kicker_match = re.search(
            r"([A-Z]\. ?[A-Z][a-z]+)\s(?:attempts an extra point|attempts a \d+\s+yards field goal|kickoff)",
            details,
        )

        punter_match = re.search(r"([A-Z]\. ?[A-Z][a-z]+)\s+punt", details)

        if kicker_match:
            return kicker_match.group(1)
        elif punter_match:
            return punter_match.group(1)

        return None

    df = df.copy()
    df["Kicker"] = df["Details"].apply(extract_kicker_or_punter)
    return df


def add_recovered_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Recovered" hinzu, die den Namen des Spielers extrahiert,
    der den Fumble recovered hat, basierend auf dem Muster:
    'Recovered by team XYZ by <Initial>. <Nachname>'

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit neuer Spalte "Recovered"
    """

    def extract_recovered(details):
        if not isinstance(details, str):
            return None
        match = re.search(
            r"Recovered by team [A-Za-z ]+ by ([A-Z]\. ?[A-Z][a-z]+)", details
        )
        return match.group(1) if match else None

    df = df.copy()
    df["Recovered"] = df["Details"].apply(extract_recovered)
    return df


def add_intercepted_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte 'Intercepted' hinzu, die den Namen des Spielers extrahiert,
    der eine Interception gemacht hat, basierend auf dem Muster:
    'pass intercepted by <Initial>. <Nachname>'
    """

    def extract_intercepted(details):
        if not isinstance(details, str):
            return None
        match = re.search(r"pass intercepted by ([A-Z]\. ?[A-Z][a-z]+)", details)
        return match.group(1) if match else None

    df = df.copy()
    df["Intercepted"] = df["Details"].apply(extract_intercepted)
    return df


def add_tackler2_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte 'Tackler 2' hinzu, die den zweiten Tackler extrahiert,
    basierend auf dem Muster: 'tackled by X. Name and Y. Name'
    """

    def extract_tackler2(details):
        if not isinstance(details, str):
            return None
        match = re.search(
            r"tackled by [A-Z]\. ?[A-Z][a-z]+ and ([A-Z]\. ?[A-Z][a-z]+)", details
        )
        return match.group(1) if match else None

    df = df.copy()
    df["Tackler 2"] = df["Details"].apply(extract_tackler2)
    return df


def add_returner_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte 'Returner' hinzu, die den Namen des Kickoff- oder Punt-Returners extrahiert,
    basierend auf dem Muster: 'returned by <Initial>. <Nachname>'
    """

    def extract_returner(details):
        if not isinstance(details, str):
            return None
        match = re.search(r"returned by ([A-Z]\. ?[A-Z][a-z]+)", details)
        return match.group(1) if match else None

    df = df.copy()
    df["Returner"] = df["Details"].apply(extract_returner)
    return df


def add_odk_column(df, expected_letter, invert=False):
    df = df.copy()
    o_char, d_char = ("O", "D") if invert else ("D", "O")
    df.insert(
        1,
        "ODK",
        df[COLUMN_POSSESION].apply(
            lambda x: d_char if x.startswith(expected_letter) else o_char
        ),
    )
    df.loc[
        df[COLUMN_PLAY_TYPE].isin(["Kickoff", "PAT", "Punt", "Field Goal"]), "ODK"
    ] = "K"

    # Setze überall "S", wo "no-play" in Details oder DN None ist
    penalty_condition = (
        df["Details"].str.contains("no-play", case=False, na=False) | df["DN"].isnull()
    )
    df.loc[penalty_condition, "ODK"] = "S"
    return df


def add_scout_depended_columns(df, scout_team, opponent_team, location):
    df = df.copy()
    df["LOCATION"] = location
    df["SCOUT"] = scout_team
    df["OPPONENT"] = opponent_team

    return df


def add_gn_ls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet die "GN/LS"-Spalte als Differenz der "YARD LN"-Spalte.

    :param df: Pandas DataFrame mit den Spalten "YARD LN" und "GN/LS"
    :return: DataFrame mit berechneter "GN/LS"-Spalte
    """

    # Sicherstellen, dass die "YARD LN"-Spalte numerisch ist
    df["YARD LN"] = pd.to_numeric(df["YARD LN"], errors="coerce")

    # Initialisieren der GN/LS-Spalte
    df["GN/LS"] = 0

    # Berechnung der GN/LS-Werte
    for i in range(1, len(df)):
        current_yard_ln = df.loc[i, "YARD LN"]
        previous_yard_ln = df.loc[i - 1, "YARD LN"]

        if df.loc[i, COLUMN_POSSESION] == df.loc[i - 1, COLUMN_POSSESION]:
            # Umwandeln in positive Werte
            previous_value = abs(previous_yard_ln)
            current_value = abs(current_yard_ln)

            # Berechnung der GN/LS-Werte
            previous_adjusted = 50 - previous_value
            current_adjusted = 50 - current_value

            # GN/LS ist die Summe der beiden angepassten Werte
            df.loc[i, "GN/LS"] = previous_adjusted + current_adjusted

    return df


def add_adjusted_yardline(df: pd.DataFrame) -> pd.DataFrame:
    def adjust_yardlines(group):
        """Passe die YARD_LN-Werte nach den angegebenen Regeln an."""
        group["YARD_LN_ADJUSTED"] = group["YARD LN"].apply(
            lambda x: -x if x < 0 else 50 - x + 50
        )
        return group

    # Anwenden der Funktion auf jede Gruppe in 'SERIES'
    df = df.groupby("SERIES").apply(adjust_yardlines)

    # Ergebnis anzeigen
    return df


def add_score_column(
    df: pd.DataFrame, scout_team: str, opponent_team: str
) -> pd.DataFrame:
    # Neue Spalten mit 0 initialisieren
    df["SCORE_SCOUT"] = 0
    df["SCORE_OPP"] = 0
    df["SCORE_DIFF"] = 0  # Neue Spalte für die Differenz

    # Score erhöhen
    score_scout = 0
    score_opp = 0
    for index, row in df.iterrows():
        if "TD" in row[COLUMN_RESULT]:
            if row["POSS"] == scout_team:
                score_scout += 6
            elif row["POSS"] == opponent_team:
                score_opp += 6

        if "Good" in row[COLUMN_RESULT]:
            if row["POSS"] == scout_team:
                if row["PLAY TYPE"] == "FG":  # Überprüfung auf Field Goal
                    score_scout += 3
                else:
                    score_scout += 1
            elif row["POSS"] == opponent_team:
                if row["PLAY TYPE"] == "FG":  # Überprüfung auf Field Goal
                    score_opp += 3
                else:
                    score_opp += 1

        if "Safety" in row[COLUMN_RESULT]:
            if row["POSS"] == scout_team:
                score_scout += 2
            elif row["POSS"] == opponent_team:
                score_opp += 2

        if "TPC" in row[COLUMN_RESULT]:  # Überprüfung auf Two-Point Conversion
            if row["POSS"] == scout_team:
                score_scout += 2
            elif row["POSS"] == opponent_team:
                score_opp += 2

        # Punkte für 'TD', 'GOOD', 'SAFETY' und 'TPC' zusammenfassen
        df.at[index, "SCORE_SCOUT"] = score_scout
        df.at[index, "SCORE_OPP"] = score_opp

        # SCORE_DIFF berechnen
        df.at[index, "SCORE_DIFF"] = score_scout - score_opp

    return df


def transform_adjusted_yardline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet die Differenz zwischen den Werten in einer bestimmten Spalte von Zeile zu Zeile.

    :param df: Pandas DataFrame
    :param column_name: Name der Spalte, für die die Differenz berechnet werden soll
    :return: DataFrame mit einer neuen Spalte "Difference", die die berechneten Differenzen enthält
    """

    column_name = "YARD_LN_ADJUSTED"

    # Sicherstellen, dass die angegebene Spalte numerisch ist
    df[column_name] = pd.to_numeric(df[column_name], errors="coerce")

    # Berechnung der Differenz und Hinzufügen zur neuen Spalte "Difference"
    df["GN/LS"] = (
        df[column_name].diff().shift(-1).fillna(0)
    )  # Erster Wert wird als 0 behandelt
    df = df.drop(columns=[column_name])

    return df


def transform_gn_ls_by_odk(df: pd.DataFrame) -> pd.DataFrame:
    # Setze den Wert in der Spalte 'GN/LS' auf 0, wo die 'ODK' Spalte den Wert 'K' hat
    df.loc[df["ODK"] == "K", "GN/LS"] = 0
    return df


def transform_play_types(expected_team: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Ändert bestimmte Werte in der Spalte "PLAY TYPE",
    wenn das Team in der Spalte "POSSESION" nicht mit expected_team übereinstimmt.

    :param expected_team: Das erwartete Team, nach dem gesucht wird
    :param df: Pandas DataFrame
    :return: DataFrame mit aktualisierten Werten in der Spalte "PLAY TYPE"
    """

    # Mapping der PLAY TYPE Werte
    play_type_mapping = {
        "KO": "KO Rec",
        "Punt": "Punt Rec",
        "Extra Pt.": "Extra Pt. Block",
    }

    # Bedingung anwenden und Mapping durchführen
    mask = df[COLUMN_POSSESION] != expected_team
    df.loc[mask, COLUMN_PLAY_TYPE] = df.loc[mask, COLUMN_PLAY_TYPE].replace(
        play_type_mapping
    )

    return df


def transform_to_short_team_code(
    df: pd.DataFrame, short_team_map: dict
) -> pd.DataFrame:
    """
    Ersetzt die Teamnamen in der Spalte "PEN O/D" des DataFrames basierend auf einem Mapping.

    Parameters
    ----------
    df : pd.DataFrame
        Der DataFrame, in dem die Ersetzungen vorgenommen werden.
    short_team_map : dict
        Ein Dictionary, das die vollständigen Teamnamen als Schlüssel und die kurzen Teamnamen als Werte enthält.

    Returns
    -------
    pd.DataFrame
        Der aktualisierte DataFrame mit den ersetzten Teamnamen in der Spalte "PEN O/D".
    """
    # Ersetzen der Teamnamen in der Spalte "PEN O/D"
    df["PEN O/D"] = df["PEN O/D"].apply(
        lambda team_string: (
            next(
                (
                    short_code
                    for full_name, short_code in short_team_map.items()
                    if full_name in team_string
                ),
                team_string,
            )
            if team_string is not None
            else team_string
        )
    )
    return df


def create_team_dataframe(game_data: dict, team: str) -> pd.DataFrame:
    """
    Erstellt ein flaches DataFrame für ein Team ('home' oder 'visitors').
    Setzt den Index als: 'Erster Buchstabe von First Name + Leerzeichen + Last Name'.

    Gibt ein DataFrame mit Spalten:
    ['First Name', 'Last Name', 'Position', '#', 'Starter', 'Team']

    Parameter:
        game_data (dict): Das gesamte Spiel-Dictionary
        team (str): 'home' oder 'visitors'
    """
    if game_data is None:
        return None
    all_players = []

    team_data = game_data
    for group in ["starter", "bench"]:
        players = team_data.get(group, [])
        for player in players:
            first_name = player.get("Index", "").strip()
            last_name = player.get("Last Name", "")
            player_entry = {
                "First Name": first_name,
                "Last Name": last_name,
                "Position": player.get("Position", ""),
                "#": player.get("#", ""),
                "Starter": "Starter" if group == "starter" else "Bench",
                "Team": team,
            }
            all_players.append(player_entry)

    df = pd.DataFrame(all_players)

    # Index setzen: erster Buchstabe von First Name + ' ' + Last Name
    df.index = df["First Name"].str[0] + " " + df["Last Name"]

    return df


def enrich_player_numbers(
    df_drive: pd.DataFrame, df_players: pd.DataFrame
) -> pd.DataFrame:
    """
    Ergänzt die Drive-Tabelle um Nummernspalten für Passer, Rusher, Receiver, Tackler.
    Verwendet weiche Nachnamenssuche: prüft, ob der Nachname aus der Drive-Tabelle
    im 'Last Name' des Spieler-DF enthalten ist.
    """

    roles = {
        "Passer": "Passer Number",
        "Rusher": "Rusher Number",
        "Receiver": "Receiver Number",
        "Tackler": "Tackler Number",
        "Kicker": "Kicker Number",
        "Recovered": "Recovered Number",
        "Intercepted": "Intercepted Number",
        "Tackler 2": "Tackler 2 Number",
        "Returner": "Returner Number",
    }

    enriched_columns = {new_col: [] for new_col in roles.values()}

    for _, row in df_drive.iterrows():
        team = row.get("POSS")

        for role_col, new_col in roles.items():
            name = row.get(role_col)

            if pd.isna(name) or pd.isna(team):
                enriched_columns[new_col].append(None)
                continue

            try:
                first_initial, last_name_part = name.split(". ")
                last_name_part = last_name_part.strip()
            except ValueError:
                enriched_columns[new_col].append(None)
                continue

            # Weiche Suche im Nachnamen
            if df_players is None:
                enriched_columns[new_col].append(None)
            else:
                matches = df_players[
                    (
                        df_players["Last Name"].str.contains(
                            last_name_part, case=False, na=False
                        )
                    )  # TODO: Achtung Gleiche Namen könnten Probleme machen
                ]

                if not matches.empty:
                    enriched_columns[new_col].append(int(matches.iloc[0]["#"]))
                else:
                    enriched_columns[new_col].append(None)

    # Neue Spalten anhängen
    df_drive = df_drive.copy()
    for col, values in enriched_columns.items():
        df_drive[col] = values

    return df_drive


def rename_player_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bennennt Spielerbezogene Spalten in ein standardisiertes Format:
    z.B. 'Passer' → 'PASSER_Name' und 'Passer Number' → 'PASSER_Jersey'

    Zusätzlich:
    - 'Receiver' → 'RECEIVER_Name'
    - 'Tackler' → 'TACKLER1_Name'
    - 'Tackler 2' → 'TACKLER2_Name'
    - 'Intercepted' → 'INTERCEPTED BY_Name'
    - 'Recovered' → 'RECOVERED BY_Name'
    - 'Returner' wird aus Receiver ersetzt
    """

    rename_map = {
        # Passer
        "Passer": "PASSER_Name",
        "Passer Number": "PASSER_Jersey",
        # Rusher
        "Rusher": "RUSHER_Name",
        "Rusher Number": "RUSHER_Jersey",
        # Receiver
        "Receiver": "RECEIVER_Name",
        "Receiver Number": "RECEIVER_Jersey",
        # Tackler 1
        "Tackler": "TACKLER1_Name",
        "Tackler Number": "TACKLER1_Jersey",
        # Tackler 2
        "Tackler 2": "TACKLER2_Name",
        "Tackler 2 Number": "TACKLER2_Jersey",
        # Kicker
        "Kicker": "KICKER_Name",
        "Kicker Number": "KICKER_Jersey",
        # Punter
        "Punter": "PUNTER_Name",
        "Punter Number": "PUNTER_Jersey",
        # Recovered
        "Recovered": "RECOVERED BY_Name",
        "Recovered Number": "RECOVERED BY_Jersey",
        # Intercepted
        "Intercepted": "INTERCEPTED BY_Name",
        "Intercepted Number": "INTERCEPTED BY_Jersey",
        # Returner → basiert auf Receiver, falls gewünscht
        "Returner": "RETURNER_Name",
        "Returner Number": "RETURNER_Jersey",
    }

    df = df.copy()
    df = df.rename(columns=rename_map)
    return df


def main():

    if "extract_button" not in st.session_state:
        st.session_state["extract_button"] = False

    st.header("Gamebook Extractor")

    with st.sidebar:
        st.subheader("Upload")
        uploaded_file = st.file_uploader(label="Upload Gamebook", type=".pdf")
        if st.button("Extract"):
            st.session_state["extract_button"] = True

    if st.session_state["extract_button"]:
        pages = extract_text_from_pdf(uploaded_file)

        doc = {}

        for i, parser in enumerate(PARSERS):
            doc = parser(pages[i], doc)

        doc = parse_last_pages(pages[5:], doc)

        st.write("---")
        st.subheader("Results")
        # Raw Data
        with st.expander("Raw Data"):
            st.write(doc)

        with st.expander("Drives Table"):
            df = dict_to_dataframe(doc.get("drives", {}))

            df = (
                df.pipe(split_down_distance)
                .pipe(transform_yardline)
                .pipe(transform_down_distance_values)
                .pipe(rename_and_reorder_columns)
                .pipe(add_play_column)
                .pipe(add_play_type)
                .pipe(add_result_column)
                .pipe(verify_fumble)
                .pipe(add_kicking_yards_column)
                .pipe(add_caught_on_column)
                .pipe(fill_in_caught_on_column)
                .pipe(add_return_yards_column)
                .pipe(split_penalty_rows)
                .pipe(add_penalty_columns)
                .pipe(add_passer_column)
                .pipe(add_rusher_column)
                .pipe(add_receiver_column)
                .pipe(add_tackler_column)
                .pipe(add_tackler2_column)
                .pipe(add_kicker_column)
                .pipe(add_returner_column)
                .pipe(add_recovered_column)
                .pipe(add_intercepted_column)
                .pipe(add_adjusted_yardline)
                .pipe(transform_adjusted_yardline)
            )

            visitors = doc.get("score_board")[0].get("Team")
            home = doc.get("score_board")[1].get("Team")
            expected_letter = home[0].upper()

            participation = doc.get("participation", None)
            short_home = NAMES.get(home).get("short")
            short_visitors = NAMES.get(visitors).get("short")

            short_team_map = {
                home: short_home,
                visitors: short_visitors,
            }

            if participation is not None:
                players_home = create_team_dataframe(
                    participation.get("home", None), short_home
                )
                players_visitors = create_team_dataframe(
                    participation.get("visitors", None), short_visitors
                )

                players = pd.concat([players_home, players_visitors], axis=0)
            else:
                players = None

            tab1, tab2 = st.tabs([home, visitors])

            with tab1:
                df_home = add_odk_column(df, expected_letter, invert=False)
                df_home = transform_gn_ls_by_odk(df_home)
                df_home = transform_play_types(short_home, df_home)
                df_home = add_scout_depended_columns(
                    df_home, short_home, short_visitors, "HOME"
                )
                df_home = enrich_player_numbers(df_home, players)
                df_home = rename_player_columns(df_home)
                df_home = add_score_column(df_home, short_home, short_visitors)
                df_home = transform_to_short_team_code(df_home, short_team_map)
                st.dataframe(df_home)

            with tab2:
                df_away = add_odk_column(df, expected_letter, invert=True)
                df_away = transform_gn_ls_by_odk(df_away)
                df_away = transform_play_types(short_visitors, df_away)
                df_away = add_scout_depended_columns(
                    df_away, short_visitors, short_home, "AWAY"
                )
                df_away = enrich_player_numbers(df_away, players)
                df_away = rename_player_columns(df_away)
                df_away = add_score_column(df_away, short_visitors, short_home)
                df_away = transform_to_short_team_code(df_away, short_team_map)
                st.dataframe(df_away)

    else:
        st.write("Kein Text gefunden oder Fehler beim Extrahieren.")

        return


# Program
if __name__ == "__main__":
    main()
