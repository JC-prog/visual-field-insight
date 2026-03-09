import fitz  # pymupdf
from PIL import Image


def convert_from_path(pdf_path, dpi=300):
    """
    Convert a PDF file to a list of PIL Images.
    No poppler required — uses pymupdf (fitz).

    Args:
        pdf_path (str | Path): Path to the PDF file.
        dpi (int): Resolution for the output images. Default is 300.

    Returns:
        list[PIL.Image.Image]: One PIL Image per PDF page.
    """
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    doc = fitz.open(str(pdf_path))
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images
