from flask import Flask, render_template, request
from docx import Document
import zipfile
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/subir', methods=['POST'])
def subir():
    if 'zip' not in request.files:
        return 'No se ha subido ningún archivo'
    
    archivo_zip = request.files['zip']
    
    if archivo_zip.filename == '':
        return 'No se ha seleccionado ningún archivo'
    
    # Guardar el ZIP temporalmente
    ruta_zip = 'temp/' + archivo_zip.filename
    os.makedirs('temp', exist_ok=True)
    archivo_zip.save(ruta_zip)
    
    # Extraer el ZIP
    ruta_extraccion = 'temp/extraido'
    os.makedirs(ruta_extraccion, exist_ok=True)
    
    with zipfile.ZipFile(ruta_zip, 'r') as zip_ref:
        zip_ref.extractall(ruta_extraccion)
    
    # Leer los archivos Word
    articulos = []
    for raiz, carpetas, archivos in os.walk(ruta_extraccion):
        for archivo in archivos:
            if archivo.endswith('.docx'):
                ruta_docx = os.path.join(raiz, archivo)
                doc = Document(ruta_docx)
                
                # Extraer texto de cada párrafo
                texto_completo = []
                for parrafo in doc.paragraphs:
                    if parrafo.text.strip():
                        texto_completo.append(parrafo.text)
                
                articulos.append({
                    'archivo': archivo,
                    'parrafos': texto_completo[:10]  # Primeros 10 párrafos
                })
    
    return render_template('resultado.html', articulos=articulos)

if __name__ == '__main__':
    app.run(debug=True)