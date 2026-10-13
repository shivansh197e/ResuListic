from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT


def docx_extract(file_path):
    """
    Extracts text and hyperlinks from a DOCX file.
    Extracts text from paragraphs, tables (preserving lines for section splitters),
    and embedded XML textboxes/shapes (used in modern two-column DOCX templates).
    Returns: (text: str, hyperlinks: list[str])
    On failure: (None, [])
    """
    text_blocks = []
    hyper_link = set()  # Using set to auto-deduplicate
    try:
        doc = Document(file_path)

        for para in doc.paragraphs:
            if para.text and para.text.strip():
                text_blocks.append(para.text.strip())

        for table in doc.tables:
            for row in table.rows:
                seen_cells = set()
                for cell in row.cells:
                    # Avoid duplicate merged cell references in python-docx
                    if id(cell._tc) in seen_cells:
                        continue
                    seen_cells.add(id(cell._tc))
                    cell_text = cell.text.strip()
                    if cell_text:
                        text_blocks.append(cell_text)

        # Also extract text from XML textboxes (w:txbxContent) if present
        try:
            for txbx in doc.element.xpath('.//*[local-name()="txbxContent"]//*[local-name()="p"]'):
                runs = [t.text for t in txbx.xpath('.//*[local-name()="t"]') if t.text]
                line = "".join(runs).strip()
                if line and line not in text_blocks:
                    text_blocks.append(line)
        except Exception:
            pass

        for rel in doc.part.rels.values():
            if rel.reltype == RT.HYPERLINK:
                hyper_link.add(rel.target_ref)

        text = "\n".join(text_blocks) + "\n"
        return text, list(hyper_link)

    except Exception as err:
        print(f"Error in docx_extract: {err}")
        return None, []