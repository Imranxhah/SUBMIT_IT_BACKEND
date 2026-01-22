import io
import pytesseract
from PIL import Image
from pptx import Presentation
from pypdf import PdfReader

def extract_content_from_file(file):
    """
    Extracts text content from the uploaded file (PDF, PPTX, Image, TXT).
    Returns a string containing the extracted text.
    """
    content = ""
    file_name = file.name.lower()

    try:
        if file_name.endswith('.txt'):
            content = file.read().decode('utf-8')

        elif file_name.endswith('.pdf'):
            reader = PdfReader(file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n\n"

        elif file_name.endswith('.pptx'):
            prs = Presentation(file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        content += shape.text + "\n"
                content += "\n--- New Slide ---\n"

        elif file_name.endswith(('.png', '.jpg', '.jpeg')):
            try:
                image = Image.open(file)
                content = pytesseract.image_to_string(image)
            except Exception as e:
                 content = f"[Error processing image: {str(e)}. Ensure Tesseract-OCR is installed on the server.]"

        else:
            content = "[Unsupported file format]"

    except Exception as e:
        content = f"[Error extracting content: {str(e)}]"

    return content
