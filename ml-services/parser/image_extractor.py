import pytesseract
from PIL import Image, ImageEnhance

pytesseract.pytesseract.tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe"
def img_extract(file_input):
    text=""
    try:
        if isinstance(file_input,str):#if it is string, it is filepath
            img= Image.open(file_input)
            opened_here=True
        else:
            img=file_input#if it is not string, pdf was changed to image and that image is sent here(i.e. an image object which is already opened is sent here)
            opened_here=False
        #greyscalling
        img=img.convert('L')
        #resizing
        wd=3*img.width
        ht=3*img.height
        img=img.resize((wd,ht),Image.Resampling.LANCZOS)
        #increasing contrast to remove blur
        enhancer=ImageEnhance.Contrast(img)
        img=enhancer.enhance(2.5)
        
        text+= pytesseract.image_to_string(img)
        if opened_here:
            img.close()
        
        return text
    except Exception as err:
        print(f"Error: {err}")
        return None

    

