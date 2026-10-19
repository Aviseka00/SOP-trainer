"""Conservative source-preserving parsing; heuristic labels are review aids."""
from __future__ import annotations
import hashlib
import io
import re
import zipfile
from .schema import CATEGORIES, validate_scene

MAX_BYTES = 25 * 1024 * 1024

def extract(filename: str, content: bytes) -> str:
    if not content or len(content) > MAX_BYTES:
        raise ValueError('Upload a nonempty document smaller than 25 MB.')
    name = filename.lower()
    if name.endswith('.pdf'):
        import fitz
        with fitz.open(stream=content, filetype='pdf') as doc:
            if doc.needs_pass:
                raise ValueError('Password-protected PDF: provide an unlocked copy.')
            text = '\n'.join(page.get_text() for page in doc)
    elif name.endswith('.docx'):
        from docx import Document
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(f.file_size for f in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError('Expanded DOCX exceeds 100 MB.')
        doc = Document(io.BytesIO(content))
        # Walk XML body order so table instructions remain between their surrounding paragraphs.
        from docx.oxml.ns import qn
        parts = []
        for element in doc.element.body:
            if element.tag == qn('w:p'):
                parts.append(''.join(node.text or '' for node in element.iter(qn('w:t'))))
            elif element.tag == qn('w:tbl'):
                for row in element.findall(qn('w:tr')):
                    parts.append(' | '.join(''.join(node.text or '' for node in cell.iter(qn('w:t'))) for cell in row.findall(qn('w:tc'))))
        text = '\n'.join(parts)
    elif name.endswith('.txt'):
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            if content.startswith((b'\xff\xfe', b'\xfe\xff')):
                text = content.decode('utf-16')
            else:
                raise ValueError('TXT must be UTF-8 or UTF-16; conversion must not silently change source wording.')
    else:
        raise ValueError('Supported source formats: PDF, DOCX and TXT.')
    if not text.strip():
        raise ValueError('No readable text. Scanned PDFs require external OCR; OCR is not included.')
    return text

def category(text: str) -> str:
    scores = {key: sum(text.lower().count(word) for word in words) for key, words in CATEGORIES.items()}
    return max(scores, key=scores.get) if max(scores.values(), default=0) else 'General'

def metadata(text: str) -> dict:
    fields = {'sop_number': r'(?im)^\s*SOP\s*(?:number|no\.?|id|#)\s*[:：-]\s*(.+)$',
              'revision': r'(?im)^\s*(?:revision|rev\.?)\s*[:：-]\s*(.+)$',
              'effective_date': r'(?im)^\s*effective\s+date\s*[:：-]\s*(.+)$',
              'title': r'(?im)^\s*(?:SOP\s+)?title\s*[:：-]\s*(.+)$'}
    return {key: (match.group(1).strip() if (match := re.search(pattern, text)) else '') for key, pattern in fields.items()}

def source_record(filename: str, content: bytes, text: str) -> dict:
    return {'filename': filename, 'sha256': hashlib.sha256(content).hexdigest(),
            'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), **metadata(text)}

def storyboard(text: str) -> list[dict]:
    if not text.strip():
        raise ValueError('Source text is empty.')
    chunks = []
    section = 'Source'
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        # Retain a numbered step as a unit: do not split quantities, abbreviations or warnings.
        number = re.match(r'^(\d+(?:\.\d+)*)(?:[.)]\s+|\s+)(.+)', line)
        if number:
            section = number.group(1)
        reference = f'Section {section} · line {line_no}' if section != 'Source' else f'Source line {line_no}'
        safety = 'prohibited' if re.search(r'\b(do not|must not|never|prohibited)\b', line, re.I) else 'critical' if re.search(r'\b(warning|caution|critical|danger|must|shall)\b', line, re.I) else 'standard'
        flags = []
        if re.search(r'\b(as appropriate|if necessary|adequate|sufficient|until clean)\b', line, re.I):
            flags.append('Ambiguous criterion: confirm against the source and SME guidance.')
        if re.match(r'(?i)^(title|SOP\s*(?:number|no|id)|revision|effective date)\s*:', line):
            flags.append('Document metadata; decide whether this belongs in spoken training.')
        entities = {'equipment': re.findall(r'\b[A-Z]{2,}(?:-\d+)+\b', line),
                    'quantities': re.findall(r'\b\d+(?:\.\d+)?\s*(?:seconds?|minutes?|hours?|mL|mg|kg|°C|%)\b', line, re.I)}
        chunks.append(validate_scene({'narration': line, 'original_instruction': line, 'visual': category(line),
                                      'reference': reference, 'source_line': line_no, 'source_section': section,
                                      'safety_classification': safety, 'flags': flags, 'entities': entities}, len(chunks)))
    if len(chunks) > 2000:
        raise ValueError('Source exceeds 2,000 segments. Split the document; no instructions were discarded.')
    return chunks

def contradiction_flags(original: str, narration: str) -> list[str]:
    flags = []
    if original != narration:
        flags.append('Narration differs from original instruction; human comparison required.')
    for token in re.findall(r'\d+(?:\.\d+)?(?:\s*%)?', original):
        if token not in narration:
            flags.append(f'Source number missing or changed: {token}')
    if re.search(r'\b(do not|must not|never|prohibited)\b', original, re.I) and not re.search(r'\b(do not|must not|never|prohibited)\b', narration, re.I):
        flags.append('Possible contradiction: source prohibition is missing.')
    return flags
