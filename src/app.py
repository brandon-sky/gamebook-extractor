# Dependencies
import re

import PyPDF2
import streamlit as st
import pandas as pd

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

    return df


def split_down_distance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Spaltet die Spalte "Down&Distance" in separate Spalten "Down" und "Distance" und entfernt die ursprüngliche Spalte.

    :param df: Pandas DataFrame mit einer Spalte "Down&Distance"
    :return: DataFrame mit zusätzlichen Spalten "Down" und "Distance" ohne "Down&Distance"
    """
    df[["Down", "Distance"]] = df["Down&Distance"].str.split("&", expand=True)
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
    return df


def rename_and_reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Umbenennung der Spalte "Index" in "Possession" und Neuanordnung der Spalten in der gewünschten Reihenfolge.

    :param df: Pandas DataFrame mit den ursprünglichen Spalten
    :return: DataFrame mit umbenannten und neu geordneten Spalten
    """
    df.rename(columns={"Index": "Possession"}, inplace=True)
    column_order = ["Drive", "Possession", "YardLine", "Down", "Distance", "Details"]
    df = df[column_order]
    return df


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
            return "Field Goal"
        elif "punt" in details_lower:
            return "Punt"
        elif "timeout" in details_lower:
            return "Timeout"
        elif "knee" in details_lower:
            return "Run"
        elif "kickoff" in details_lower:
            return "Kickoff"
        elif "extra point" in details_lower:
            return "PAT"
        return "Other"

    df["Play Type"] = df["Details"].apply(categorize_play)
    return df


def add_result_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Result" hinzu, die den Ausgang des Spielzugs basierend auf der "Details"-Spalte kategorisiert.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "Result"-Spalte
    """

    def categorize_result(details):
        details_lower = details.lower()
        if "rush" in details_lower or "knee" in details_lower:
            return "Rush"
        elif "incomplete" in details_lower:
            return "Incomplete"
        elif "complete" in details_lower:
            return "Complete"
        elif "sacked" in details_lower:
            return "Sack"
        elif "intercepted" in details_lower:
            return "Interception"
        elif "is good" in details_lower:
            return "Good"
        elif "no good" in details_lower:
            return "No good"
        elif "returned" in details_lower:
            return "Return"
        elif "fair catch" in details_lower:
            return "Fair Catch"
        elif "timeout" in details_lower:
            return "Timeout"
        return "Other"

    df["Result"] = df["Details"].apply(categorize_result)
    return df


def add_passer_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fügt eine neue Spalte "Passer" hinzu, die den Namen des Passgebers extrahiert.

    :param df: Pandas DataFrame mit einer "Details"-Spalte
    :return: DataFrame mit der neuen "Passer"-Spalte
    """
    import re

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


def add_odk_column(df, expected_letter, invert=False):
    df = df.copy()
    o_char, d_char = ('D', 'O') if invert else ('O', 'D')
    df.insert(0, 'ODK', df['Possession'].apply(lambda x: d_char if x.startswith(expected_letter) else o_char))
    df.loc[df['Play Type'].isin(['Kickoff', 'PAT', 'Punt', 'Field Goal']), 'ODK'] = 'K'

    penalty_condition = df['Details'].str.contains('penalty', case=False, na=False) \
                        & ~df['Details'].str.contains('declined', case=False, na=False)
    df.loc[penalty_condition, 'ODK'] = 'S'
    return df


def update_play_type(df):
    df = df.copy()
    for i in range(len(df)):
        if df.loc[i, 'Play Type'] in ['Punt', 'Kickoff']:
            if 'D' in df.loc[i+1:i+5, 'ODK'].values:
                df.loc[i, 'Play Type'] = 'Punt Return' if df.loc[i, 'Play Type'] == 'Punt' else 'Kick Off Return'
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
                .pipe(rename_and_reorder_columns)
                .pipe(add_play_type)
                .pipe(add_result_column)
                .pipe(add_passer_column)
                .pipe(add_rusher_column)
                .pipe(add_receiver_column)
                .pipe(add_tackler_column)
            )

            visitors = doc.get("score_board")[0].get("Team")
            home = doc.get("score_board")[1].get("Team")
            expected_letter = home[0].upper()
            
            tab1, tab2 = st.tabs([home, visitors])
            
            with tab1:
                df_home = add_odk_column(df, expected_letter, invert=False)
                df_home = update_play_type(df_home)
                st.dataframe(df_home)

            with tab2:
                df_away = add_odk_column(df, expected_letter, invert=True)
                df_away = update_play_type(df_away)
                st.dataframe(df_away)

    else:
        st.write("Kein Text gefunden oder Fehler beim Extrahieren.")

        return


# Program
if __name__ == "__main__":
    main()
