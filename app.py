from flask import Flask, render_template, request
from docx import Document
import zipfile
import os
import mysql.connector
import fitz  # PyMuPDF

app = Flask(__name__)

config_db = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'db_xml'
}

# Etiquetas del Word
ETIQUETAS = {
    'title_en': 'Título completo en inglés:',
    'title_es': 'Título completo en español:',
    'title_abr_en': 'Título abreviado (solo inglés):',
    'doi': 'DOI:',
    'fecha_recepcion': 'Fecha de recepción:',
    'fecha_aceptacion': 'Fecha de aceptación:',
    'keywords_en': 'Palabras clave en inglés:',
    'keywords_es': 'Palabras clave en español:',
    'email_correspondencia': 'Autor y e-mail de correspondencia:',
    'abstract_en': 'Abstract en inglés:',
    'abstract_es': 'Resumen en español:',
}

def procesar_word(ruta_docx):
    doc = Document(ruta_docx)

    datos = {k: '' for k in ETIQUETAS}
    autores = []
    leyendo_autores = False

    for p in doc.paragraphs:
        texto = p.text.strip()
        if not texto:
            continue

        # Detectar sección de autores
        if 'Autores/ Filiación' in texto:
            leyendo_autores = True
            continue

        if leyendo_autores:
            if any(etiqueta in texto for etiqueta in ETIQUETAS.values()):
                leyendo_autores = False
            else:
                if texto:
                    autores.append(texto)
                continue

        # Extraer campos por etiqueta
        for campo, etiqueta in ETIQUETAS.items():
            if etiqueta in texto:
                datos[campo] = texto.split(etiqueta)[1].strip()
                break

    datos['autores'] = autores
    return datos

def insertar_en_bd(datos, journal_id):
    try:
        conexion = mysql.connector.connect(**config_db)
        cursor = conexion.cursor()

        # Extraer journal_id del DOI
        doi = datos['doi'].replace('https://doi.org/', '')

        # Convertir fechas de DD/MM/YYYY a YYYY-MM-DD
        def convertir_fecha(fecha_str):
            if not fecha_str:
                return None
            try:
                partes = fecha_str.strip().split('/')
                return f"{partes[2]}-{partes[1]}-{partes[0]}"
            except:
                return None

        received = convertir_fecha(datos['fecha_recepcion'])
        accepted = convertir_fecha(datos['fecha_aceptacion'])

        # Insertar artículo
        query = """INSERT INTO article 
            (article_title, article_title_trans, doi, journal_id, license_type, 
            abstract, trans_abstract, received, accepted) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(query, (
            datos['title_es'],
            datos['title_en'],
            doi,
            journal_id,
            'open-access',
            datos['abstract_es'],
            datos['abstract_en'],
            received,
            accepted
        ))
        article_id = cursor.lastrowid

        # Insertar keywords EN
        if datos['keywords_en']:
            for kw in datos['keywords_en'].split(','):
                kw = kw.strip()
                if kw:
                    cursor.execute(
                        "INSERT INTO keywords (article_id, lang, kwd) VALUES (%s, %s, %s)",
                        (article_id, 'en', kw)
                    )

        # Insertar keywords ES
        if datos['keywords_es']:
            for kw in datos['keywords_es'].split(','):
                kw = kw.strip()
                if kw:
                    cursor.execute(
                        "INSERT INTO keywords (article_id, lang, kwd) VALUES (%s, %s, %s)",
                        (article_id, 'es', kw)
                    )

        conexion.commit()
        cursor.close()
        conexion.close()
        return True

    except Exception as e:
        return str(e)
    
def extraer_texto_pdf(ruta_pdf):
    texto = ''
    doc = fitz.open(ruta_pdf)
    for pagina in doc:
        texto += pagina.get_text()
    doc.close()
    texto = ' '.join(texto.split())
    return texto

def comparar_con_pdf(datos, texto_pdf):
    resultados = []

    def buscar(valor, texto):
        if not valor:
            return 'VACÍO EN WORD'
        return 'COINCIDE' if valor.lower() in texto.lower() else 'NO COINCIDE'

    resultados.append({'campo': 'Título en español', 'valor': datos['title_es'], 'resultado': buscar(datos['title_es'], texto_pdf)})
    resultados.append({'campo': 'Título en inglés', 'valor': datos['title_en'], 'resultado': buscar(datos['title_en'], texto_pdf)})
    resultados.append({'campo': 'DOI', 'valor': datos['doi'], 'resultado': buscar(datos['doi'], texto_pdf)})
    resultados.append({'campo': 'Keywords EN', 'valor': datos['keywords_en'], 'resultado': buscar(datos['keywords_en'], texto_pdf)})
    resultados.append({'campo': 'Keywords ES', 'valor': datos['keywords_es'], 'resultado': buscar(datos['keywords_es'], texto_pdf)})

    # Comparar autores uno a uno
    for autor in datos['autores']:
        resultados.append({'campo': 'Autor', 'valor': autor, 'resultado': buscar(autor, texto_pdf)})

    return resultados

@app.route('/')
def index():
    try:
        conexion = mysql.connector.connect(**config_db)
        cursor = conexion.cursor()
        cursor.execute("SELECT journal_id FROM journal")
        journals = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conexion.close()
    except:
        journals = []
    return render_template('index.html', journals=journals)

@app.route('/subir', methods=['POST'])
def subir():
    if 'word' not in request.files:
        return 'No se ha subido ningún archivo'

    archivo_word = request.files['word']

    if archivo_word.filename == '':
        return 'No se ha seleccionado ningún archivo'

    if not archivo_word.filename.endswith('.docx'):
        return 'El archivo debe ser un Word (.docx)'

    os.makedirs('temp', exist_ok=True)
    ruta_docx = 'temp/' + archivo_word.filename
    archivo_word.save(ruta_docx)

    journal_id = request.form.get('journal_id', 'desconocido')
    datos = procesar_word(ruta_docx)

    if datos['title_es'] and datos['doi']:
        # Verificar si el DOI ya existe en la BD
        doi_limpio = datos['doi'].replace('https://doi.org/', '')
        try:
            conexion = mysql.connector.connect(**config_db)
            cursor = conexion.cursor()
            cursor.execute("SELECT article_id FROM article WHERE doi = %s", (doi_limpio,))
            existe = cursor.fetchone()
            cursor.close()
            conexion.close()
        except:
            existe = None

        if existe:
            resultados = [{
                'archivo': archivo_word.filename,
                'datos': datos,
                'insertado': False,
                'error': 'Este artículo ya existe en la BD con el DOI: ' + doi_limpio,
                'comparacion': []
            }]
            return render_template('resultado.html', resultados=resultados)

        resultado_bd = insertar_en_bd(datos, journal_id)
        
@app.route('/articulos')
def articulos():
    try:
        conexion = mysql.connector.connect(**config_db)
        cursor = conexion.cursor()
        cursor.execute("SELECT article_id, article_title, article_title_trans, doi, journal_id, received, accepted FROM article ORDER BY article_id DESC")
        articulos = cursor.fetchall()
        cursor.close()
        conexion.close()
    except:
        articulos = []
    return render_template('articulos.html', articulos=articulos)

if __name__ == '__main__':
    app.run(debug=True)