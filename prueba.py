import mysql.connector
from docx import Document

config_db = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'db_xml'   
}

doc = Document('v38n2a2.docx')

DOI = "DOI:"
TITLE_EN = "Título completo en inglés:"
TITLE_ES = "Título completo en español:"
TITLE_ABR_EN = "Título abreviado (solo inglés):"
ABSTRACT_EN = "Abstract en inglés:"
ABSTRACT_ES = "Resumen en español:"

title_en = ''
title_es = ''
title_abr_en = ''
doi = ''
abstract_en = ''
abstract_es = ''

for p in doc.paragraphs:
    texto = p.text.strip()
    if TITLE_EN in texto:
        title_en = texto.split(TITLE_EN)[1].strip()
    if TITLE_ES in texto:
        title_es = texto.split(TITLE_ES)[1].strip()
    if TITLE_ABR_EN in texto:
        title_abr_en = texto.split(TITLE_ABR_EN)[1].strip()
    if DOI in texto:
        doi = texto.split(DOI)[1].strip()
    if ABSTRACT_EN in texto:
        abstract_en = texto.split(ABSTRACT_EN)[1].strip()
    if ABSTRACT_ES in texto:
        abstract_es = texto.split(ABSTRACT_ES)[1].strip()
        

print("Título ES:", title_es)
print("Título EN:", title_en)
print("DOI:", doi)
print("Abstract ES:", abstract_es[:100])
print("Abstract EN:", abstract_en[:100])