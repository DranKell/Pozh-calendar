# -*- coding: utf-8 -*-
"""
Утилита для извлечения текстового содержимого из файлов документов:
- DOCX (.docx, .doc)
- EXCEL (.xlsx, .xls)
- PDF (.pdf)
- Текстовые файлы (.txt, .csv, .json)
"""
import io
import logging
from typing import Optional

logger = logging.getLogger("doc_parser")


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """
    Извлекает весь текст из переданного файла (байты + имя файла).
    """
    name_lower = filename.lower()
    text = ""

    # 1. EXCEL (.xlsx, .xlsm, .xltx)
    if name_lower.endswith((".xlsx", ".xlsm", ".xltx")):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
            lines = []
            for sheet in wb.worksheets:
                lines.append(f"--- Лист: {sheet.title} ---")
                for row in sheet.iter_rows(values_only=True):
                    row_vals = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
                    if row_vals:
                        lines.append(" | ".join(row_vals))
            text = "\n".join(lines)
            if text.strip():
                return text
        except Exception as e:
            logger.warning("Ошибка openpyxl при парсинге %s: %s", filename, e)

    # 2. WORD (.docx)
    if name_lower.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            lines = []
            for p in doc.paragraphs:
                pt = p.text.strip()
                if pt:
                    lines.append(pt)
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if row_cells:
                        lines.append(" | ".join(row_cells))
            text = "\n".join(lines)
            if text.strip():
                return text
        except Exception as e:
            logger.warning("Ошибка docx при парсинге %s: %s", filename, e)

    # 3. PDF (.pdf)
    if name_lower.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            lines = []
            for idx, page in enumerate(reader.pages):
                pt = page.extract_text() or ""
                if pt.strip():
                    lines.append(f"--- Страница {idx + 1} ---")
                    lines.append(pt.strip())
            text = "\n".join(lines)
            if text.strip():
                return text
        except Exception as e:
            logger.warning("Ошибка pypdf при парсинге %s: %s", filename, e)

    # 4. Текстовые файлы или fallback для бинарных (.txt, .csv, .json, старый .doc/.xls как текст)
    for enc in ["utf-8", "windows-1251", "cp866", "latin-1"]:
        try:
            decoded = file_bytes.decode(enc)
            # Фильтруем читаемые печатные символы
            printable = "".join(ch for ch in decoded if ch.isprintable() or ch in "\n\r\t")
            if len(printable) > 20:
                return printable
        except UnicodeDecodeError:
            continue

    return text
