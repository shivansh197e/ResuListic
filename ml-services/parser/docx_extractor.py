from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
def docx_extract(file_path):
    text=""
    hyper_link=[]
    try:
        doc=Document(file_path)#in this library, we don't need to use with open because it will also autometically closes the file preventing memory leaks
        for para in doc.paragraphs:
            text+= para.text + "\n"
            for rel in para.part.rels.values():
                if rel.reltype==RT.HYPERLINK:
                    hyper_link.append(rel.target_ref)
        return text,hyper_link
    except Exception as err:
        print(f"Error: {err}")
        return None,[]