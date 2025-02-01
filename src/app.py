# Dependencies
import PyPDF2
import streamlit as st

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


def main():

    st.header("Gamebook Extractor")

    st.subheader("Upload")
    uploaded_file = st.file_uploader(label="Upload Gamebook", type=".pdf")

    if st.button("Extract"):
        if uploaded_file is not None:
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

        else:
            st.write("Kein Text gefunden oder Fehler beim Extrahieren.")

    return


# Program
if __name__ == "__main__":
    main()
