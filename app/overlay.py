import fitz  # PyMuPDF
from pathlib import Path
from .models import TextAnnotation, LeaderLineAnnotation, Annotation

BLUE = (0, 0, 1)

TEXT_WIDTH_FACTOR = 0.60
LINE_HEIGHT_FACTOR = 1.25
PADDING = 6


def estimate_text_box(ann: TextAnnotation):
    lines = ann.text.split("\n")
    max_chars = max((len(line) for line in lines), default=1)
    width = max_chars * ann.fontSize * TEXT_WIDTH_FACTOR + 2 * PADDING
    height = len(lines) * ann.fontSize * LINE_HEIGHT_FACTOR + 2 * PADDING
    x0 = ann.x - PADDING
    y0 = ann.y - ann.fontSize - PADDING
    x1 = x0 + width
    y1 = y0 + height
    return fitz.Rect(x0, y0, x1, y1)


def get_title_block_zone(page: fitz.Page) -> fitz.Rect:
    rect = page.rect
    x0 = rect.x0 + rect.width * 0.68
    y0 = rect.y0 + rect.height * 0.78
    x1 = rect.x1
    y1 = rect.y1
    return fitz.Rect(x0, y0, x1, y1)


def rects_overlap(a: fitz.Rect, b: fitz.Rect) -> bool:
    return not (a.x1 < b.x0 or a.x0 > b.x1 or a.y1 < b.y0 or a.y0 > b.y1)


def validate_text_annotation(page: fitz.Page, ann: TextAnnotation, used_boxes: list[fitz.Rect]) -> None:
    box = estimate_text_box(ann)
    page_rect = page.rect
    title_block = get_title_block_zone(page)

    if box.x0 < page_rect.x0 or box.y0 < page_rect.y0 or box.x1 > page_rect.x1 or box.y1 > page_rect.y1:
        raise ValueError(f'Text annotation "{ann.text}" is outside page bounds')

    if rects_overlap(box, title_block):
        raise ValueError(f'Text annotation "{ann.text}" falls in protected title block zone')

    for used in used_boxes:
        if rects_overlap(box, used):
            raise ValueError(f'Text annotation "{ann.text}" overlaps another annotation')

    used_boxes.append(box)


def validate_leader_line(page: fitz.Page, ann: LeaderLineAnnotation) -> None:
    page_rect = page.rect
    for pt in ann.points:
        if pt.x < page_rect.x0 or pt.x > page_rect.x1 or pt.y < page_rect.y0 or pt.y > page_rect.y1:
            raise ValueError("Leader line point is outside page bounds")


def draw_text(page: fitz.Page, ann: TextAnnotation) -> None:
    page.insert_text(
        fitz.Point(ann.x, ann.y),
        ann.text,
        fontsize=ann.fontSize,
        color=BLUE,
        overlay=True,
    )


def draw_leader_line(page: fitz.Page, ann: LeaderLineAnnotation) -> None:
    if len(ann.points) < 2:
        raise ValueError("Leader line must have at least 2 points")

    shape = page.new_shape()
    for i in range(len(ann.points) - 1):
        p1 = ann.points[i]
        p2 = ann.points[i + 1]
        shape.draw_line(fitz.Point(p1.x, p1.y), fitz.Point(p2.x, p2.y))

    shape.finish(color=BLUE, width=ann.strokeWidth)
    shape.commit(overlay=True)


def apply_annotations_to_pdf(
    input_pdf: Path,
    output_pdf: Path,
    annotations: list[Annotation],
    page_number_1_based: int,
) -> None:
    doc = fitz.open(input_pdf)
    try:
        page = doc.load_page(page_number_1_based - 1)
        used_boxes = []

        for ann in annotations:
            if ann.pageNumber != page_number_1_based:
                continue

            if hasattr(ann, "kind") and ann.kind == "text":
                validate_text_annotation(page, ann, used_boxes)
                draw_text(page, ann)
            elif hasattr(ann, "kind") and ann.kind == "leader_line":
                validate_leader_line(page, ann)
                draw_leader_line(page, ann)

        doc.save(output_pdf)
    finally:
        doc.close()


def render_pdf_page_to_png(input_pdf: Path, output_png: Path, page_number_1_based: int, dpi: int = 200) -> None:
    doc = fitz.open(input_pdf)
    try:
        page = doc.load_page(page_number_1_based - 1)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pix.save(output_png)
    finally:
        doc.close()
