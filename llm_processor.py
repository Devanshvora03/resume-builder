# llm_processor.py
from groq import Groq
import os
from io import BytesIO
import pdfplumber
import docx
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Groq client with API key from environment
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    logger.error("GROQ_API_KEY not found in environment variables")
    raise ValueError("GROQ_API_KEY is required")
groq_client = Groq(api_key=groq_api_key)

# Load preamble from file
with open('preamble.tex', 'r', encoding='utf-8') as f:
    latex_preamble = f.read()

latex_closing = r"\end{document}"

def extract_text_from_pdf(content_bytes: bytes) -> str:
    try:
        with pdfplumber.open(BytesIO(content_bytes)) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            extracted_text = text.strip()
            logger.info("Successfully extracted text from PDF")
            return extracted_text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return None

def extract_text_from_docx(content_bytes: bytes) -> str:
    try:
        doc = docx.Document(BytesIO(content_bytes))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        extracted_text = text.strip()
        logger.info("Successfully extracted text from DOCX")
        return extracted_text
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        return None

def generate_latex_with_groq(extracted_text: str) -> str:
    try:
        prompt = f"""
Convert the following resume text into a structured LaTeX format using the provided template structure. Use ONLY the following commands: \section, \resumeSubheading, \resumeItem, \resumeSubHeadingListStart, \resumeSubHeadingListEnd, \resumeItemListStart, \resumeItemListEnd. Do NOT invent new commands like \resumeHeader. Structure the content into sections: Education, Work Experience, Skills, Projects, Certifications (if present), and Co-Curricular (if present). Wrap \resumeSubheading and \resumeItem within the appropriate list environments (\resumeSubHeadingListStart/\resumeSubHeadingListEnd for subheadings, \resumeItemListStart/\resumeItemListEnd for items). Include a header with the name, email, phone, and optional links (e.g., GitHub, LinkedIn) using \begin{{center}}...\end{{center}}. Here’s the input text:

{extracted_text}

Provide only the content between \begin{{document}} and \end{{document}}. Ensure every \resumeSubheading has four arguments (e.g., {{Institution}}{{Dates}}{{Degree}}{{Location}}) and every \resumeItem has one argument. If data is missing, use empty strings (e.g., ""). Replace special characters like ⋄ with $|$, and escape % as \%. Do not include the preamble or \end{{document}}. Return plain LaTeX content without additional comments or explanations.
"""
        response = groq_client.chat.completions.create(
            model="qwen-2.5-coder-32b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        latex_content = response.choices[0].message.content.strip()
        full_latex = latex_preamble + latex_content + latex_closing
        logger.info("Successfully generated LaTeX code")
        return full_latex
    except Exception as e:
        logger.error(f"Error generating LaTeX: {e}")
        return None