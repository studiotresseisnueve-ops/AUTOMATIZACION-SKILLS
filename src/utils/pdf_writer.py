"""
PDF Report Writer — generates professional PDF reports using fpdf2.
"""
import logging
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

logger = logging.getLogger(__name__)

# ── Colour palette ──────────────────────────────────────────────────────────
COLOR_PRIMARY   = (30, 80, 160)    # deep blue
COLOR_SECONDARY = (60, 60, 60)     # dark grey
COLOR_ACCENT    = (220, 230, 245)  # light blue fill (section headings)
COLOR_LINE      = (180, 180, 180)  # light grey rule
COLOR_TABLE_ALT = (240, 245, 252)  # very light blue (alternating table rows)
COLOR_WHITE     = (255, 255, 255)

# ── Layout constants ─────────────────────────────────────────────────────────
MARGIN_L  = 18
MARGIN_R  = 18
PAGE_W    = 210
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R   # 174 mm

# ── Inline-marker regex ──────────────────────────────────────────────────────
_RE_BOLD   = re.compile(r'\*\*(.+?)\*\*')
_RE_ITALIC = re.compile(r'\*(.+?)\*')
_RE_CODE   = re.compile(r'`(.+?)`')
_RE_LINK   = re.compile(r'\[(.+?)\]\(.+?\)')


# Common Unicode characters that fall outside latin-1 but have close equivalents
_UNICODE_MAP = str.maketrans({
    '\u2018': "'",  '\u2019': "'",   # curly single quotes
    '\u201C': '"',  '\u201D': '"',   # curly double quotes
    '\u2013': '-',  '\u2014': '-',   # en-dash, em-dash
    '\u2026': '...',                 # ellipsis
    '\u2022': '-',  '\u00B7': '-',   # bullet, middle dot
    '\u25CF': '-',  '\u25E6': '-',   # filled/empty circle bullets
    '\u2212': '-',                   # minus sign
    '\u00A0': ' ',                   # non-breaking space
    '\u00AB': '"',  '\u00BB': '"',   # guillemets
})


def _safe(text: str) -> str:
    """Map common Unicode characters to latin-1 equivalents, then encode."""
    return text.translate(_UNICODE_MAP).encode("latin-1", errors="replace").decode("latin-1")


def _strip_inline(text: str) -> str:
    """Remove common inline markdown markers, returning plain text."""
    text = _RE_BOLD.sub(r'\1', text)
    text = _RE_ITALIC.sub(r'\1', text)
    text = _RE_CODE.sub(r'\1', text)
    text = _RE_LINK.sub(r'\1', text)
    return text


def _count_lines(pdf: FPDF, text: str, width: float,
                 font: str = "Helvetica", style: str = "", size: float = 9) -> int:
    """Estimate the number of lines ``text`` occupies inside ``width`` mm."""
    pdf.set_font(font, style, size)
    clean = _safe(_strip_inline(text)).strip()
    if not clean:
        return 1
    usable = max(width - 2, 1)
    space_w = pdf.get_string_width(" ")
    lines, line_w = 1, 0.0
    for word in clean.split():
        ww = pdf.get_string_width(word)
        if line_w > 0 and line_w + space_w + ww > usable:
            lines += 1
            line_w = ww
        else:
            line_w = (line_w + space_w + ww) if line_w else ww
    return lines


# ─────────────────────────────────────────────────────────────────────────────

class PDFReportWriter:
    """Generates a structured, professional PDF report for a single skill result."""

    def generate_report(
        self,
        output_path: str | Path,
        company_name: str,
        skill_name: str,
        content: str,
    ) -> None:
        """
        Build and save a PDF report.

        Args:
            output_path: Destination file path (created if missing).
            company_name: Name of the analysed company.
            skill_name: Name of the skill / analysis type.
            content: Full text output from the skill agent.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(left=MARGIN_L, top=MARGIN_L, right=MARGIN_R)
        pdf.add_page()

        self._draw_header(pdf, company_name, skill_name)
        logger.debug(
            "PDF content preview for '%s/%s': %s",
            company_name, skill_name,
            content[:300].replace('\n', '↵'),
        )
        self._draw_content(pdf, content)
        self._draw_footer(pdf)

        pdf.output(str(output_path))
        logger.info("PDF saved: %s", output_path)

    # ── Header / Footer ───────────────────────────────────────────────────────

    def _draw_header(self, pdf: FPDF, company_name: str, skill_name: str) -> None:
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.rect(0, 0, PAGE_W, 38, "F")

        pdf.set_text_color(*COLOR_WHITE)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_xy(MARGIN_L, 8)
        pdf.cell(CONTENT_W, 10, _safe(skill_name.replace("_", " ").title()), new_x="LMARGIN", new_y="NEXT", align="C")

        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(MARGIN_L, 20)
        pdf.cell(CONTENT_W, 8, _safe(f"Empresa: {company_name}"), new_x="LMARGIN", new_y="NEXT", align="C")

        pdf.set_font("Helvetica", "I", 9)
        pdf.set_xy(MARGIN_L, 29)
        ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        pdf.cell(CONTENT_W, 7, _safe(f"Generado: {ts}"), new_x="LMARGIN", new_y="NEXT", align="C")

        pdf.set_text_color(*COLOR_SECONDARY)
        pdf.set_xy(MARGIN_L, 44)

    def _draw_footer(self, pdf: FPDF) -> None:
        pdf.set_y(-14)
        pdf.set_draw_color(*COLOR_LINE)
        pdf.set_line_width(0.3)
        pdf.line(MARGIN_L, pdf.get_y(), PAGE_W - MARGIN_R, pdf.get_y())
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 6, _safe("Generado automaticamente por el Sistema de Agentes Autonomos"), align="C")

    # ── Content dispatcher ────────────────────────────────────────────────────

    def _draw_content(self, pdf: FPDF, content: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COLOR_SECONDARY)

        lines = content.split("\n")
        i = 0
        in_code_block = False
        code_lines: list[str] = []

        while i < len(lines):
            raw = lines[i].rstrip()

            # ── Code block (``` ... ```) ───────────────────────────────────
            if raw.lstrip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_lines = []
                else:
                    in_code_block = False
                    if code_lines:
                        # If the "code block" is actually a pipe table, render it as one
                        if any(line.strip().startswith("|") for line in code_lines):
                            self._draw_table(pdf, code_lines)
                        else:
                            self._draw_code_block(pdf, code_lines)
                    code_lines = []
                i += 1
                continue

            if in_code_block:
                code_lines.append(raw)
                i += 1
                continue

            # ── Markdown table block ──────────────────────────────────────
            if raw.lstrip().startswith("|") and "|" in raw.lstrip()[1:]:
                table_block: list[str] = []
                while i < len(lines) and lines[i].rstrip().lstrip().startswith("|"):
                    table_block.append(lines[i].rstrip())
                    i += 1
                self._draw_table(pdf, table_block)
                continue

            # ── Headings (allow optional leading whitespace) ───────────────
            stripped = raw.lstrip()
            if stripped.startswith("#### "):
                self._subsection_heading(pdf, stripped[5:])
            elif stripped.startswith("### "):
                self._subsection_heading(pdf, stripped[4:])
            elif stripped.startswith("## "):
                self._section_heading(pdf, stripped[3:])
            elif stripped.startswith("# "):
                self._top_heading(pdf, stripped[2:])

            # ── **Standalone bold line** treated as subsection heading ────
            elif re.match(r'^\*\*[^*]+\*\*\s*$', stripped):
                self._subsection_heading(pdf, stripped.strip('*').strip())

            # ── Lists (with optional leading whitespace) ──────────────────
            # Handles: "- text", "* text", "-**bold** text"
            elif re.match(r'^\s*[-*][\s*]', raw) and not re.match(r'^\s*\*\*', raw):
                text = re.sub(r'^\s*[-*]\*?\*?', '', raw).lstrip()
                indent = len(raw) - len(raw.lstrip())
                self._bullet(pdf, text, indent_level=min(indent // 2, 3))
            elif re.match(r'^\s*\d+\.\s', raw):
                m = re.match(r'^\s*(\d+)\.\s+(.*)', raw)
                if m:
                    self._numbered_item(pdf, int(m.group(1)), m.group(2))

            # ── Blank line ────────────────────────────────────────────────
            elif raw.strip() == "":
                pdf.ln(3)

            # ── Normal paragraph ──────────────────────────────────────────
            else:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(*COLOR_SECONDARY)
                pdf.multi_cell(0, 5.5, _safe(_strip_inline(raw)))
                pdf.ln(1)

            i += 1

        # Flush unclosed code block
        if in_code_block and code_lines:
            self._draw_code_block(pdf, code_lines)

    # ── Heading helpers ───────────────────────────────────────────────────────

    def _top_heading(self, pdf: FPDF, text: str) -> None:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.multi_cell(0, 7, _safe(_strip_inline(text)))
        y = pdf.get_y()
        pdf.set_draw_color(*COLOR_PRIMARY)
        pdf.set_line_width(0.6)
        pdf.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
        pdf.ln(3)
        pdf.set_text_color(*COLOR_SECONDARY)

    def _section_heading(self, pdf: FPDF, text: str) -> None:
        pdf.ln(3)
        pdf.set_fill_color(*COLOR_ACCENT)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.multi_cell(0, 7, _safe(f"  {_strip_inline(text)}"), fill=True)
        pdf.ln(2)
        pdf.set_text_color(*COLOR_SECONDARY)

    def _subsection_heading(self, pdf: FPDF, text: str) -> None:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.multi_cell(0, 6, _safe(_strip_inline(text)))
        y = pdf.get_y()
        pdf.set_draw_color(*COLOR_LINE)
        pdf.set_line_width(0.3)
        pdf.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
        pdf.ln(2)
        pdf.set_text_color(*COLOR_SECONDARY)

    # ── List helpers ──────────────────────────────────────────────────────────

    def _bullet(self, pdf: FPDF, text: str, indent_level: int = 0) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COLOR_SECONDARY)
        indent = MARGIN_L + 4 + indent_level * 5
        bullet_char = "\u2022" if indent_level == 0 else "\u25e6"
        pdf.set_x(indent)
        pdf.cell(4, 5.5, _safe(bullet_char), new_x="RIGHT", new_y="TOP")
        text_w = PAGE_W - MARGIN_R - indent - 4
        pdf.multi_cell(text_w, 5.5, _safe(_strip_inline(text)), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.5)

    def _numbered_item(self, pdf: FPDF, num: int, text: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COLOR_SECONDARY)
        pdf.set_x(MARGIN_L + 4)
        pdf.cell(6, 5.5, _safe(f"{num}."), new_x="RIGHT", new_y="TOP")
        text_w = PAGE_W - MARGIN_R - MARGIN_L - 10
        pdf.multi_cell(text_w, 5.5, _safe(_strip_inline(text)), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.5)

    def _draw_code_block(self, pdf: FPDF, lines: list[str]) -> None:
        """Render a fenced code block as a shaded box with monospaced text."""
        if not lines:
            return
        pdf.ln(2)
        pdf.set_fill_color(240, 240, 240)
        pdf.set_draw_color(*COLOR_LINE)
        pdf.set_line_width(0.3)
        pdf.set_font("Courier", "", 8.5)
        pdf.set_text_color(*COLOR_SECONDARY)
        for line in lines:
            clean = _safe(line) if line.strip() else " "
            pdf.multi_cell(CONTENT_W, 5, clean, border=0, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COLOR_SECONDARY)

    # ── Table rendering ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_table(table_lines: list[str]) -> tuple[list[str] | None, list[list[str]]]:
        """Split markdown pipe-table lines into (header_row, body_rows)."""
        header: list[str] | None = None
        body: list[list[str]] = []

        for line in table_lines:
            # Split on | and strip
            parts = [c.strip() for c in line.split("|")]
            # Remove artefacts from leading / trailing |
            if parts and parts[0] == "":
                parts = parts[1:]
            if parts and parts[-1] == "":
                parts = parts[:-1]

            if not parts:
                continue

            # Separator row  (---  :---:  etc.)
            if all(re.match(r'^[-: ]+$', p) for p in parts):
                continue

            cells = [_strip_inline(p) for p in parts]
            if header is None:
                header = cells
            else:
                body.append(cells)

        return header, body

    @staticmethod
    def _compute_col_widths(
        header: list[str] | None,
        body: list[list[str]],
        available: float,
    ) -> list[float]:
        """Distribute available width proportionally to max-content-length per column."""
        all_rows = ([header] if header else []) + body
        n_cols = max((len(r) for r in all_rows), default=1)

        # Use character-count as a proxy for needed width
        max_len = [0] * n_cols
        for row in all_rows:
            for j, cell in enumerate(row[:n_cols]):
                max_len[j] = max(max_len[j], len(cell))

        total = sum(max_len) or n_cols
        min_w = 14.0
        widths = [max(min_w, available * l / total) for l in max_len]

        # Normalise so widths sum exactly to `available`
        scale = available / sum(widths)
        return [w * scale for w in widths]

    def _draw_table(self, pdf: FPDF, table_lines: list[str]) -> None:
        header, body = self._parse_table(table_lines)
        if header is None and not body:
            return

        pdf.ln(3)

        col_widths = self._compute_col_widths(header, body, CONTENT_W)
        line_h = 5.0   # height per text line inside a cell

        # ── Header row ────────────────────────────────────────────────────
        if header:
            self._render_table_row(
                pdf, header, col_widths,
                fill_color=COLOR_PRIMARY,
                text_color=COLOR_WHITE,
                font_style="B", font_size=8.5,
                line_h=line_h,
            )

        # ── Body rows ─────────────────────────────────────────────────────
        pdf.set_draw_color(*COLOR_LINE)
        for idx, row in enumerate(body):
            fill = COLOR_TABLE_ALT if idx % 2 == 0 else COLOR_WHITE
            self._render_table_row(
                pdf, row, col_widths,
                fill_color=fill,
                text_color=COLOR_SECONDARY,
                font_style="", font_size=8.5,
                line_h=line_h,
            )

        pdf.ln(4)

    def _render_table_row(
        self,
        pdf: FPDF,
        cells: list[str],
        col_widths: list[float],
        fill_color: tuple,
        text_color: tuple,
        font_style: str,
        font_size: float,
        line_h: float,
    ) -> None:
        """Render one table row, sizing the row height to fit the tallest cell."""
        n = len(col_widths)

        # ── Compute required height ───────────────────────────────────────
        max_lines = 1
        for j in range(n):
            cell_text = cells[j] if j < len(cells) else ""
            n_lines = _count_lines(pdf, cell_text, col_widths[j], size=font_size, style=font_style)
            max_lines = max(max_lines, n_lines)

        row_h = max_lines * line_h + 2   # +2 mm vertical padding

        # ── Page-break guard ─────────────────────────────────────────────
        if pdf.get_y() + row_h > pdf.h - pdf.b_margin:
            pdf.add_page()

        x0 = MARGIN_L
        y0 = pdf.get_y()

        pdf.set_font("Helvetica", font_style, font_size)
        pdf.set_fill_color(*fill_color)
        pdf.set_text_color(*text_color)
        pdf.set_draw_color(*COLOR_LINE)
        pdf.set_line_width(0.2)

        # ── Draw each cell ────────────────────────────────────────────────
        for j in range(n):
            cell_text = cells[j] if j < len(cells) else ""
            x = x0 + sum(col_widths[:j])
            pdf.set_xy(x, y0)
            pdf.multi_cell(
                col_widths[j], line_h,
                _safe(cell_text),
                border=1,
                fill=True,
                align="L",
                new_x="RIGHT",
                new_y="TOP",
                max_line_height=line_h,
            )

        # Advance cursor past this row
        pdf.set_xy(x0, y0 + row_h)
