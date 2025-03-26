from flask import Flask, render_template, request, send_file, flash
from werkzeug.utils import secure_filename
import subprocess
from pathlib import Path
import os
import io
import shutil

app = Flask(__name__)
app.secret_key = "supersecretkey"

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
            return None, False, "Error: pdflatex not found in environment."
        
        cmd = ['pdflatex', '-interaction=nonstopmode', str(tex_file)]
        for _ in range(2):
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=temp_dir,
                env={**os.environ, "HOME": str(temp_dir)} if os.name != 'nt' else os.environ
            )
            if process.returncode != 0:
                return None, False, f"pdflatex failed with error:\n{process.stderr}"
        
        if pdf_file.exists():
            with open(pdf_file, 'rb') as f:
                pdf_bytes = f.read()
            return pdf_bytes, True, "PDF generated successfully!"
        else:
            return None, False, "PDF generation failed: No PDF file produced.\n" + process.stderr
    
    except Exception as e:
        return None, False, f"Error: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file uploaded.")
            return render_template('index.html', output_name="document")
        
        file = request.files['file']
        if file.filename == '':
            flash("No file selected.")
            return render_template('index.html', output_name="document")
        
        output_name = request.form.get('output_name', 'document')
        if not output_name:
            output_name = 'document'
        output_name = secure_filename(output_name)
        
        file_content = file.read().decode('utf-8')
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Use Render's PORT or default to 5000
    app.run(host='0.0.0.0', port=port, debug=True)