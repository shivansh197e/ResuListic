from docx import Document

def docx_extract(file_path):
    text=""
    try:
        doc=Document(file_path)#in this library, we don't need to use with open because it will also autometically closes the file preventing memory leaks
        for para in doc.paragraphs:
            text+= para.text + "\n"
        return text
    except Exception as err:
        print(f"Error: {err}")
        return None


    