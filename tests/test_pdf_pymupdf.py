"""Test PDF handler with PyMuPDF."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cat_tool.formats.pdf import PdfHandler


def test_pdf_handler():
    """Test PDF load and render."""
    with tempfile.TemporaryDirectory() as td:
        # Create a simple test PDF using PyMuPDF
        import fitz
        pdf_path = os.path.join(td, "test.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Hello world.", fontsize=12)
        page.insert_text((50, 80), "This is a test.", fontsize=12)
        page.insert_text((50, 110), "Third line here.", fontsize=12)
        doc.save(pdf_path)
        doc.close()
        print(f"Created test PDF: {pdf_path}")
        
        # Load with handler
        handler = PdfHandler()
        segments = handler.load(pdf_path)
        print(f"Loaded {len(segments)} segments:")
        for i, seg in enumerate(segments):
            print(f"  {i}: {seg['source']} (page {seg['source_location'].get('page')})")
        
        # Add translations
        segments[0]["target"] = "Hola mundo."
        segments[1]["target"] = "Esto es una prueba."
        segments[2]["target"] = "Tercera línea aquí."
        
        # Render
        output_path = os.path.join(td, "test_translated.pdf")
        handler.render(pdf_path, segments, output_path)
        print(f"Rendered translated PDF: {output_path}")
        
        # Verify output
        doc2 = fitz.open(output_path)
        text = ""
        for page in doc2:
            text += page.get_text()
        doc2.close()
        
        # Don't print text (encoding issues), just verify
        print(f"Output text length: {len(text)} chars")
        
        if "Hola mundo." in text and "Esto es una prueba." in text:
            print("\n[OK] PDF translation works!")
            return True
        else:
            print("\n[FAIL] Translations not found in output")
            print(f"  Looking for: 'Hola mundo.' and 'Esto es una prueba.'")
            return False


if __name__ == "__main__":
    test_pdf_handler()