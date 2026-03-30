"""
OCR – Utilidades compartidas de preprocesamiento
=================================================
"""

from PIL import Image, ImageFilter, ImageEnhance


def _otsu_threshold(image: Image.Image) -> int:
    """Calcula el umbral óptimo de binarización con el método de Otsu."""
    hist = image.histogram()
    total = sum(hist)
    sum_all = sum(i * hist[i] for i in range(256))
    sum_b = wb = 0
    best_var = best_t = 0
    for t in range(256):
        wb += hist[t]
        if not wb:
            continue
        wf = total - wb
        if not wf:
            break
        sum_b += t * hist[t]
        mb = sum_b / wb
        mf = (sum_all - sum_b) / wf
        var = wb * wf * (mb - mf) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return best_t


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    w2, h2 = image.size
    image = image.resize((w2 * 4, h2 * 4), Image.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(3.0)
    image = image.filter(ImageFilter.SHARPEN)
    image = image.filter(ImageFilter.SHARPEN)
    threshold = _otsu_threshold(image)
    image = image.point(lambda p: 255 if p < threshold else 0)
    return image
