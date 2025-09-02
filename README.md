# Digital Automation Scaffold

This repository provides scripts, templates, and a minimal dashboard for digitizing operations of a small construction company.

## Contents
- `src/ocr/receipt_ocr.py` – Extracts raw text from receipt images using Tesseract OCR and writes JSON files.
- `src/ocr/job_assigner.py` – Command‑line helper to tag receipt line items with job IDs and save a new CSV.
- `src/dashboard/app.py` – Flask web dashboard for uploading receipts and viewing stored files.
- `excel_templates/` – CSV templates for fuel logs and job quotes that can be opened in Excel or Google Sheets.
- `Dockerfile` – Builds a container image based on `python:3.11.9-slim-bullseye` with Tesseract and the project scripts.
- `k8s/deployment.yaml` – Example Kubernetes deployment and service for the dashboard.

## Branches
- `development` – active branch where all ongoing work is merged.
- `main` – stable branch kept in sync with `development`.

## Setup
1. Install [Tesseract OCR](https://tesseract-ocr.github.io/) and ensure the `tesseract` command is available.
2. Install Python dependencies:
   ```bash
   pip install pillow pytesseract flask
   ```

## Usage
### Extract data from receipt images
Run the OCR script on one or more image files:
```bash
python src/ocr/receipt_ocr.py receipt1.jpg receipt2.png
```
Each image produces a `*.json` file containing the extracted text.

### Assign job IDs to line items
Provide a CSV (for example, exported from a parsed receipt) and enter job IDs interactively:
```bash
python src/ocr/job_assigner.py receipt.csv
```
The tool writes a new file `<receipt>_tagged.csv` with the added `job_id` column.

### Launch the web dashboard
Start the Flask application to upload and review receipt files:
```bash
python src/dashboard/app.py
```
Open <http://localhost:5000> in your browser and use the form to upload receipts.
Uploaded files appear below the form with the text that Tesseract extracted so you can verify the classification.

### Run with Docker
Build a container image and launch the dashboard:
```bash
docker build -t automation-dashboard .
docker run -p 5000:5000 automation-dashboard
```

### Deploy to Kubernetes
Push the built image to a registry and update `k8s/deployment.yaml` with that image name. Deploy the resources:

```bash
kubectl apply -f k8s/deployment.yaml
```

The service exposes the dashboard on port 80 and forwards traffic to the Flask app on port 5000.

### Fuel logs and quotes
Duplicate the CSV templates in `excel_templates/` to track fuel expenses and generate job quotes in Excel or Google Sheets.

## Notes
These scripts are starting points; expand them with additional parsing, data storage, or integrations as needed.

----------

# Andamiaje de Automatización Digital

Este repositorio proporciona scripts, plantillas y un panel mínimo para digitalizar operaciones de una pequeña empresa de construcción.

## Contenido
- `src/ocr/receipt_ocr.py` – Extrae texto sin procesar de imágenes de recibos usando Tesseract OCR y escribe archivos JSON.
- `src/ocr/job_assigner.py` – Herramienta de línea de comandos para etiquetar con IDs de trabajo los elementos de los recibos y guardar un nuevo CSV.
- `src/dashboard/app.py` – Panel web en Flask para subir recibos y ver archivos almacenados.
- `excel_templates/` – Plantillas CSV para registros de combustible y cotizaciones de trabajos que pueden abrirse en Excel o Google Sheets.
- `Dockerfile` – Construye una imagen basada en `python:3.11.9-slim-bullseye` con Tesseract y los scripts del proyecto.
- `k8s/deployment.yaml` – Ejemplo de despliegue y servicio de Kubernetes para el panel.

## Ramas
- `development` – rama activa donde se fusiona el trabajo en curso.
- `main` – rama estable sincronizada con `development`.

## Configuración
1. Instala [Tesseract OCR](https://tesseract-ocr.github.io/) y asegúrate de que el comando `tesseract` esté disponible.
2. Instala las dependencias de Python:
   ```bash
   pip install pillow pytesseract flask
   ```

## Uso
### Extraer datos de imágenes de recibos
Ejecuta el script de OCR en uno o más archivos de imagen:
```bash
python src/ocr/receipt_ocr.py receipt1.jpg receipt2.png
```
Cada imagen produce un archivo `*.json` con el texto extraído.

### Asignar IDs de trabajo a los elementos
Proporciona un CSV (por ejemplo, exportado de un recibo analizado) e introduce los IDs de trabajo de manera interactiva:
```bash
python src/ocr/job_assigner.py receipt.csv
```
La herramienta escribe un nuevo archivo `<receipt>_tagged.csv` con la columna `job_id` añadida.

### Lanzar el panel web
Inicia la aplicación Flask para subir y revisar archivos de recibos:
```bash
python src/dashboard/app.py
```
Abre <http://localhost:5000> en tu navegador y usa el formulario para subir recibos.

### Ejecutar con Docker
Construye una imagen de contenedor y lanza el panel:
```bash
docker build -t automation-dashboard .
docker run -p 5000:5000 automation-dashboard
```

### Desplegar en Kubernetes
Sube la imagen construida a un registro y actualiza `k8s/deployment.yaml` con ese nombre de imagen. Despliega los recursos:
```bash
kubectl apply -f k8s/deployment.yaml
```
El servicio expone el panel en el puerto 80 y reenvía el tráfico a la aplicación Flask en el puerto 5000.

### Registros de combustible y cotizaciones
Duplica las plantillas CSV en `excel_templates/` para registrar gastos de combustible y generar cotizaciones en Excel o Google Sheets.

## Notas
Estos scripts son puntos de partida; amplíalos con análisis adicional, almacenamiento de datos o integraciones según sea necesario.

