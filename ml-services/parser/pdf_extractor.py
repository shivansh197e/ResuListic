import pdfplumber
import re

def file_loader():
    loc=r"C:\Users\Asus\Downloads\resume_sample_student8ea47e04a8fe67e6b7acff0000376a3b.pdf"

    with pdfplumber.open(loc) as pdf:
        page=pdf.pages[0]
        text= page.extract_text()

        print(text)
        for line in text.split('\n'):
            print(line)

if __name__ == "__main__":
    file_loader()