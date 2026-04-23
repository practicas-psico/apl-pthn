from flask import Flask, render_template, request
from docx import Document
import os
import mysql.connector
import fitz

app = Flask(__name__)

config_db = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'psicofundacion'
}

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

def obtener_formato(p):
    texto_con_formato = ""
    for run in p.runs:
        contenido = run.text.replace('\xa0', ' ')
        if run.bold:
            contenido = f"<b>{contenido}</b>"
        if run.italic:
            contenido = f"<i>{contenido}</i>"
        if run.font.superscript:
            contenido = f"<sup>{contenido}</sup>"
        if run.font.subscript:
            contenido = f"<sub>{contenido}</sub>"
        texto_con_formato += contenido
    return texto_con_formato

def procesar_word(ruta_docx):
    doc = Document(ruta_docx)
    datos = {k: '' for k in ETIQUETAS}
    autores = []
    leyendo_autores = False
    leyendo_body = False
    body = []

    for p in doc.paragraphs:
        texto = p.text.strip()
        if not texto:
            continue

        if leyendo_body:
            body.append(obtener_formato(p))
            continue

        if 'Autores/ Filiación' in texto:
            leyendo_autores = True
            continue

        if leyendo_autores:
            if any(etiqueta in texto for etiqueta in ETIQUETAS.values()):
                leyendo_autores = False
            else:
                autores.append(texto)
                continue

        for campo, etiqueta in ETIQUETAS.items():
            if etiqueta in texto:
                formato = obtener_formato(p)
                if etiqueta in formato:
                    datos[campo] = formato.split(etiqueta)[1].strip()
                else:
                    datos[campo] = texto.split(etiqueta)[1].strip()
                if campo == 'abstract_es':
                    leyendo_body = True
                    print("ACTIVANDO BODY")
                break

    print("BODY LEIDO:", len(body), "párrafos")
    print("PRIMER PÁRRAFO:", body[0] if body else "VACÍO")

    datos['autores'] = autores
    datos['body'] = body
    return datos

def insertar_en_bd(datos, journal_id):
    try:
        conexion = mysql.connector.connect(**config_db)
        cursor = conexion.cursor()

        doi = datos['doi'].replace('https://doi.org/', '').strip()

        try:
            partes_doi = doi.split('/')
            journal_id = partes_doi[1].split('.')[0] if len(partes_doi) > 1 else journal_id
        except:
            pass

        cursor.execute("SELECT journal_id FROM journal WHERE journal_id = %s", (journal_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO journal (journal_id, journal_title) VALUES (%s, %s)",
                (journal_id, journal_id)
            )

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

        query = """INSERT INTO article 
            (article_title, article_title_trans, doi, journal_id, license_type, 
            abstract, trans_abstract, received, accepted, volume, issue) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(query, (
            datos['title_es'],
            datos['title_en'],
            doi,
            journal_id,
            'open-access',
            datos['abstract_es'],
            datos['abstract_en'],
            received,
            accepted,
            datos.get('volume', ''),
            datos.get('issue', '')
        ))
        article_id = cursor.lastrowid

        if datos['keywords_en']:
            for kw in datos['keywords_en'].split(','):
                kw = kw.strip()
                if kw:
                    cursor.execute(
                        "INSERT INTO keywords (article_id, lang, kwd) VALUES (%s, %s, %s)",
                        (article_id, 'en', kw)
                    )

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

@app.route('/')
def index():
    journals = []
    try:
        conexion = mysql.connector.connect(**config_db)
        cursor = conexion.cursor()
        cursor.execute("SELECT journal_id FROM journal")
        journals = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conexion.close()
    except Exception as e:
        print("ERROR BD:", e)
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
    volume = request.form.get('volume', '')
    issue = request.form.get('issue', '')
    datos = procesar_word(ruta_docx)
    datos['volume'] = volume
    datos['issue'] = issue

    if datos['title_es'] and datos['doi']:
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
        resultados = [{
            'archivo': archivo_word.filename,
            'datos': datos,
            'insertado': resultado_bd == True,
            'error': resultado_bd if resultado_bd != True else '',
            'comparacion': []
        }]
    else:
        resultados = [{
            'archivo': archivo_word.filename,
            'datos': datos,
            'insertado': False,
            'error': 'No se encontró título en español o DOI',
            'comparacion': []
        }]

    return render_template('resultado.html', resultados=resultados)

@app.route('/articulos')
def articulos():
    try:
        conexion = mysql.connector.connect(**config_db)
        cursor = conexion.cursor()
        cursor.execute("SELECT article_id, article_title, article_title_trans, doi, journal_id, received, accepted FROM article ORDER BY article_id DESC")
        arts = cursor.fetchall()
        cursor.close()
        conexion.close()
    except:
        arts = []
    return render_template('articulos.html', articulos=arts)

if __name__ == '__main__':
    app.run(debug=True)