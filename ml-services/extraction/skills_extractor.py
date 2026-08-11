import spacy


def extract_skill(text):
    nlp=spacy.load("en_core_web_md")
    doc=nlp(text)

    print(nlp.analyze_pipes())
    
extract_skill("Python, Machine Learning, NLP")