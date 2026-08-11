from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT


def docx_extract(file_path):
    """
    Extracts text and hyperlinks from a DOCX file.
    Also extracts text from tables (many resume templates use tables for layout).
    Returns: (text: str, hyperlinks: list[str])
    On failure: (None, [])
    """
    text = ""
    hyper_link = set()  # Using set to auto-deduplicate
    try:
        doc = Document(file_path)
 
        for para in doc.paragraphs:
            text += para.text + "\n"
 
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text:
                        row_text.append(cell_text)
                if row_text:
                    text += " | ".join(row_text) + "\n"
 
        for rel in doc.part.rels.values():
            if rel.reltype == RT.HYPERLINK:
                hyper_link.add(rel.target_ref)

        return text, list(hyper_link)

    except Exception as err:
        print(f"Error in docx_extract: {err}")
        return None, []