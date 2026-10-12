import pdfplumber


def pdf_extract(file_path):
    """
    Extracts text and hyperlinks from a PDF file.
    Returns: (text: str, hyperlinks: list[str])
    On failure: (None, [])
    """
    text = ""
    hyper_link = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                # page.extract_text() returns None for image-only pages
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

                if page.hyperlinks:
                    for link in page.hyperlinks:
                        if 'uri' in link:
                            hyper_link.append(link['uri'])

            seen = set()
            unique_links = []
            for link in hyper_link:
                if link not in seen:
                    seen.add(link)
                    unique_links.append(link)

            return text, unique_links

    except Exception as err:
        print(f"Error in pdf_extract: {err}")
        return None, []