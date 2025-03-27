from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import subprocess
from pathlib import Path
import os
import io
import shutil
import logging
from llm_processor import extract_text_from_pdf, extract_text_from_docx, generate_latex_with_groq

if os.getenv("RENDER"):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
else:
    logging.basicConfig(
        filename='app.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "your-secret-key"  

def create_pdf_from_file(file_content, output_filename='output'):
    temp_dir = Path("temp_latex")
    temp_dir.mkdir(exist_ok=True)
    
    tex_file = temp_dir / f"{output_filename}.tex"
    pdf_file = temp_dir / f"{output_filename}.pdf"
    
    tex_file = tex_file.absolute()
    pdf_file = pdf_file.absolute()
    
    with open(tex_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(file_content)
    
    try:
        pdflatex_path = shutil.which('pdflatex')
        if not pdflatex_path:
            logger.error("pdflatex not found in environment")
            return None, False, "Error: pdflatex not found in environment."
        
        cmd = ['pdflatex', '-interaction=nonstopmode', str(tex_file)]
        process_output = ""
        for _ in range(2):
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=temp_dir,
                env={**os.environ, "HOME": str(temp_dir), "TEXMFVAR": str(temp_dir / ".texmf-var")} if os.name != 'nt' else os.environ
            )
            process_output += f"Run {_+1} - Error:\n{process.stderr}\nOutput:\n{process.stdout}\n"
        
        if pdf_file.exists():
            with open(pdf_file, 'rb') as f:
                pdf_bytes = f.read()
            logger.info(f"PDF generated successfully for {output_filename}")
            return pdf_bytes, True, "PDF generated successfully! (Warnings may have occurred:)\n" + process_output
        else:
            logger.error(f"PDF generation failed: No PDF file produced.\n{process_output}")
            return None, False, f"PDF generation failed: No PDF file produced.\n{process_output}"
    
    except Exception as e:
        logger.error(f"Error in create_pdf_from_file: {str(e)}")
        return None, False, f"Error: {str(e)}"

@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('upload_pdf'))

@app.route('/latex-to-pdf', methods=['GET', 'POST'])
def latex_to_pdf():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file uploaded.")
            logger.warning("No file uploaded to /latex-to-pdf")
            return render_template('index.html', output_name="document")
        
        file = request.files['file']
        if file.filename == '':
            flash("No file selected.")
            logger.warning("No file selected for /latex-to-pdf")
            return render_template('index.html', output_name="document")
        
        output_name = request.form.get('output_name', 'document')
        if not output_name:
            output_name = 'document'
        output_name = secure_filename(output_name)
        
        file_content = file.read().decode('utf-8')
        logger.info(f"Processing LaTeX file: {output_name}")
        pdf_bytes, success, message = create_pdf_from_file(file_content, output_name)
        
        if success and pdf_bytes:
            flash("PDF generated successfully!")
            return send_file(
                io.BytesIO(pdf_bytes),
                download_name=f"{output_name}.pdf",
                mimetype="application/pdf",
                as_attachment=True
            )
        else:
            flash(message)
    
    return render_template('index.html', output_name="document")

@app.route('/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file uploaded.")
            logger.warning("No file uploaded to /upload_pdf")
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash("No file selected.")
            logger.warning("No file selected for /upload_pdf")
            return redirect(request.url)
        
        filename = secure_filename(file.filename)
        file_bytes = file.read()
        logger.info(f"Received file: {filename}")
        
        # Extract text based on file type
        if filename.endswith('.pdf'):
            extracted_text = extract_text_from_pdf(file_bytes)
        elif filename.endswith('.docx'):
            extracted_text = extract_text_from_docx(file_bytes)
        else:
            flash("Unsupported file type. Please upload a PDF or DOCX file.")
            logger.error(f"Unsupported file type: {filename}")
            return redirect(request.url)
        
        if not extracted_text:
            flash("Failed to extract text from the file.")
            logger.error(f"Text extraction failed for {filename}")
            return redirect(request.url)
        
        logger.info(f"Extracted text from {filename}:\n{extracted_text}")
        
        # Generate LaTeX using Groq
        latex_code = generate_latex_with_groq(extracted_text)
        if not latex_code:
            flash("Failed to generate LaTeX code.")
            logger.error(f"LaTeX generation failed for {filename}")
            return redirect(request.url)
        
        logger.info(f"Generated LaTeX code for {filename}:\n{latex_code}")
        
        # Convert LaTeX to PDF
        pdf_bytes, success, message = create_pdf_from_file(latex_code, "resume")
        if success and pdf_bytes:
            flash("PDF generated successfully!")
            logger.info(f"PDF conversion successful for {filename}")
            return send_file(
                io.BytesIO(pdf_bytes),
                download_name="resume.pdf",
                mimetype="application/pdf",
                as_attachment=True
            )
        else:
            flash(message or "Failed to generate PDF.")
            logger.error(f"PDF conversion failed for {filename}: {message}")
            return redirect(request.url)
    
    return render_template('upload_pdf.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)