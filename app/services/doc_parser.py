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
    Извлекает весь читаемый текст из переданного файла (байты + имя файла).
    Автоматически определяет формат по расширению и по магическим сигнатурам (PK.., %PDF-).
    """
    name_lower = filename.lower()
    text = ""
    is_zip = file_bytes.startswith(b"PK\x03\x04")
    is_pdf = file_bytes.startswith(b"%PDF-")

    # 1. WORD (.docx или архив с сигнатурой PK\x03\x04 и признаками docx)
    if name_lower.endswith(".docx") or (is_zip and (b"word/" in file_bytes[:3000] or name_lower.endswith(".doc"))):
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
                    # Извлекаем ячейки, удаляя дубли при объединении ячеек (row.cells могут указывать на один и тот же объект)
                    seen_cells = set()
                    row_cells = []
                    for c in row.cells:
                        ct = c.text.strip()
                        c_id = id(c._tc)
                        if c_id not in seen_cells and ct:
                            seen_cells.add(c_id)
                            row_cells.append(ct.replace("\n", " ").strip())
                    if row_cells:
                        lines.append(" | ".join(row_cells))
            text = "\n".join(lines)
            if text.strip():
                return text
        except Exception as e:
            logger.warning("Ошибка docx при парсинге %s: %s", filename, e)

    # 2. EXCEL (.xlsx, .xlsm, .xltx или ZIP с xl/)
    if name_lower.endswith((".xlsx", ".xlsm", ".xltx")) or (is_zip and b"xl/" in file_bytes[:3000]):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
            lines = []
            for sheet in wb.worksheets:
                lines.append(f"--- Лист: {sheet.title} ---")
                for row in sheet.iter_rows(values_only=True):
                    row_vals = [str(cell).strip().replace("\n", " ") for cell in row if cell is not None and str(cell).strip()]
                    if row_vals:
                        lines.append(" | ".join(row_vals))
            text = "\n".join(lines)
            if text.strip():
                return text
        except Exception as e:
            logger.warning("Ошибка openpyxl при парсинге %s: %s", filename, e)

    # 3. PDF (.pdf или сигнатура %PDF-)
    if name_lower.endswith(".pdf") or is_pdf:
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

    # 4. Если это ZIP-архив, но ни docx, ни xlsx не распарсились — НЕ декодируем бинарник как текст!
    if is_zip:
        logger.warning("Файл %s является zip-архивом, но специализированные парсеры docx/xlsx не смогли его прочесть", filename)
        return ""

    # 5. Текстовые файлы (.txt, .csv, .json, .tsv)
    for enc in ["utf-8", "windows-1251", "cp866", "latin-1"]:
        try:
            decoded = file_bytes.decode(enc)
            # Проверяем на бинарный мусор (если слишком много непечатных символов)
            printable = "".join(ch for ch in decoded if ch.isprintable() or ch in "\n\r\t")
            if len(printable) > 20 and (len(printable) / max(len(decoded), 1)) > 0.85:
                return printable
        except UnicodeDecodeError:
            continue

    return text
