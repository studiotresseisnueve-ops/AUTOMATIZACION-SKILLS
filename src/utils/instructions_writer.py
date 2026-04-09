"""
Instructions PDF Writer — generates a reference PDF that explains what
information the input company PDF must contain for each skill to work correctly.

Generated once on startup, saved to outputs/instructions/.
"""
import logging
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from src.utils.pdf_writer import (
    _safe,
    _strip_inline,
    _count_lines,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_ACCENT,
    COLOR_TABLE_ALT,
    COLOR_LINE,
    COLOR_WHITE,
    CONTENT_W,
    MARGIN_L,
    MARGIN_R,
    PAGE_W,
)

logger = logging.getLogger(__name__)

# ── Skill .md section patterns ────────────────────────────────────────────────
_RE_FRONTMATTER   = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
_RE_WHEN_TO_USE   = re.compile(r'## When to Use This Skill\s*\n(.*?)(?=\n## |\Z)', re.DOTALL)
_RE_REQUIRED_TBL  = re.compile(r'### Required Inputs\s*\n(.*?)(?=\n###|\n##|\Z)', re.DOTALL)
_RE_STEP1         = re.compile(r'## Step 1: Understand\s*\n(.*?)(?=\*\*GATE|\n## |\Z)', re.DOTALL)
_RE_NUMBERED_ITEM = re.compile(r'^\d+\.\s+\*\*(.+?)\*\*\s*[—\-]\s*(.*)')
_RE_TABLE_SEP     = re.compile(r'^\|[-: |]+\|$')


# ─────────────────────────────────────────────────────────────────────────────
#  Skill .md parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_frontmatter(raw: str) -> dict[str, str]:
    m = _RE_FRONTMATTER.match(raw)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip().strip('"')
    return result


def _parse_use_cases(raw: str) -> list[str]:
    """Return bullet items from 'When to Use This Skill', stopping at 'DO NOT'."""
    m = _RE_WHEN_TO_USE.search(raw)
    if not m:
        return []
    section = m.group(1)
    do_not = section.find("**DO NOT**")
    if do_not > 0:
        section = section[:do_not]
    items = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(_strip_inline(stripped[2:]))
    return items


def _parse_required_inputs(raw: str) -> list[dict[str, str]]:
    """
    Extract required input fields from either:
      - '### Required Inputs' pipe-table  (auditoria_pagina_web, auditoria_automatizacion)
      - '## Step 1: Understand' numbered list (analisis_competencia, auditoria_social_media)
    Returns list of dicts with keys: field, description, default.
    """
    inputs: list[dict[str, str]] = []

    # ── Try table format first ────────────────────────────────────────────
    m = _RE_REQUIRED_TBL.search(raw)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line.startswith("|") or _TABLE_SEP_LINE(line):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) < 2:
                continue
            field = _strip_inline(cells[0])
            if not field or field.lower() == "input":
                continue   # skip header row
            inputs.append({
                "field":       field,
                "description": _strip_inline(cells[1]),
                "default":     _strip_inline(cells[2]) if len(cells) > 2 else "",
            })

    # ── Fall back to numbered-list format ─────────────────────────────────
    if not inputs:
        m = _RE_STEP1.search(raw)
        if m:
            for line in m.group(1).splitlines():
                nm = _RE_NUMBERED_ITEM.match(line.strip())
                if nm:
                    inputs.append({
                        "field":       _strip_inline(nm.group(1)),
                        "description": _strip_inline(nm.group(2)),
                        "default":     "",
                    })

    return inputs


def _TABLE_SEP_LINE(line: str) -> bool:
    return bool(_RE_TABLE_SEP.match(line))


def parse_skill_file(md_path: Path) -> dict:
    """Return a structured dict of the key info from a skill .md file."""
    raw = md_path.read_text(encoding="utf-8")
    fm  = _parse_frontmatter(raw)

    display_name = (
        fm.get("name", md_path.stem)
        .replace("-", " ")
        .title()
    )

    return {
        "name":            display_name,
        "description":     fm.get("description", ""),
        "use_cases":       _parse_use_cases(raw),
        "required_inputs": _parse_required_inputs(raw),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  PDF generation
# ─────────────────────────────────────────────────────────────────────────────

class InstructionsWriter:
    """
    Generates a single reference PDF listing what each skill needs.
    The document is written to ``outputs/instructions/`` on startup.
    """

    def generate(self, output_path: str | Path, prompts_dir: str | Path) -> None:
        """
        Build and save the instructions PDF.

        Args:
            output_path: Full path for the PDF file.
            prompts_dir: Directory containing the skill .md files.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        skills = self._load_skills(Path(prompts_dir))
        if not skills:
            logger.warning("No skill .md files found in '%s' — instructions PDF not generated.", prompts_dir)
            return

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(left=MARGIN_L, top=MARGIN_L, right=MARGIN_R)
        pdf.add_page()

        self._draw_cover(pdf, len(skills))

        for skill in skills:
            self._draw_skill_section(pdf, skill)

        self._draw_footer_note(pdf)
        self._apply_footer(pdf)

        pdf.output(str(output_path))
        logger.info("Instructions PDF saved: %s", output_path)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _load_skills(prompts_dir: Path) -> list[dict]:
        if not prompts_dir.exists():
            return []
        return [parse_skill_file(p) for p in sorted(prompts_dir.glob("*.md"))]

    # ── Sections ──────────────────────────────────────────────────────────────

    def _draw_cover(self, pdf: FPDF, n_skills: int) -> None:
        # Banner
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.rect(0, 0, PAGE_W, 50, "F")

        pdf.set_text_color(*COLOR_WHITE)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_xy(MARGIN_L, 10)
        pdf.cell(CONTENT_W, 12, _safe("Guia de Informacion Requerida"), new_x="LMARGIN", new_y="NEXT", align="C")

        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(MARGIN_L, 24)
        pdf.cell(CONTENT_W, 8, _safe("Sistema de Agentes Autonomos de Analisis de Marca"), new_x="LMARGIN", new_y="NEXT", align="C")

        pdf.set_font("Helvetica", "I", 9)
        pdf.set_xy(MARGIN_L, 34)
        ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        pdf.cell(CONTENT_W, 7, _safe(f"Generado: {ts}"), new_x="LMARGIN", new_y="NEXT", align="C")

        pdf.set_text_color(*COLOR_SECONDARY)
        pdf.set_xy(MARGIN_L, 58)

        # Intro paragraph
        intro = (
            f"Este documento describe la informacion que debe contener el PDF de cada empresa "
            f"para que las {n_skills} habilidades de analisis produzcan resultados precisos. "
            "Cuando un dato no esta disponible en el PDF, el agente lo busca automaticamente "
            "en internet — pero entre mas completo sea el PDF de entrada, mayor sera la "
            "precision del analisis."
        )
        pdf.set_x(MARGIN_L)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(CONTENT_W, 5.5, _safe(intro))
        pdf.ln(4)

        # Visual rule
        pdf.set_draw_color(*COLOR_LINE)
        pdf.set_line_width(0.4)
        pdf.line(MARGIN_L, pdf.get_y(), PAGE_W - MARGIN_R, pdf.get_y())
        pdf.ln(5)

    def _draw_skill_section(self, pdf: FPDF, skill: dict) -> None:
        # ── Skill heading ──────────────────────────────────────────────────
        pdf.set_x(MARGIN_L)
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*COLOR_WHITE)
        pdf.multi_cell(CONTENT_W, 8, _safe(f"  {skill['name']}"), fill=True)
        pdf.set_x(MARGIN_L)
        pdf.set_text_color(*COLOR_SECONDARY)
        pdf.ln(2)

        # ── Description ────────────────────────────────────────────────────
        if skill["description"]:
            pdf.set_x(MARGIN_L)
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(CONTENT_W, 5, _safe(skill["description"]))
            pdf.ln(2)

        # ── What it produces ───────────────────────────────────────────────
        if skill["use_cases"]:
            pdf.set_x(MARGIN_L)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COLOR_PRIMARY)
            pdf.cell(CONTENT_W, 5.5, _safe("Que produce este analisis:"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*COLOR_SECONDARY)
            pdf.set_font("Helvetica", "", 9)
            for item in skill["use_cases"][:5]:
                pdf.set_x(MARGIN_L + 4)
                pdf.cell(4, 5, _safe("\u2022"), new_x="RIGHT", new_y="TOP")
                pdf.multi_cell(CONTENT_W - 8, 5, _safe(item))
            pdf.ln(2)

        # ── Required inputs table ──────────────────────────────────────────
        pdf.set_x(MARGIN_L)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(CONTENT_W, 5.5, _safe("Informacion requerida en el PDF de entrada:"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        if skill["required_inputs"]:
            self._draw_inputs_table(pdf, skill["required_inputs"])
        else:
            pdf.set_x(MARGIN_L)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*COLOR_SECONDARY)
            pdf.multi_cell(CONTENT_W, 5, _safe("Este skill obtiene toda la informacion via busqueda web."))

        pdf.ln(5)

        # Separator rule
        pdf.set_x(MARGIN_L)
        pdf.set_draw_color(*COLOR_LINE)
        pdf.set_line_width(0.3)
        pdf.line(MARGIN_L, pdf.get_y(), PAGE_W - MARGIN_R, pdf.get_y())
        pdf.ln(5)

    def _draw_inputs_table(self, pdf: FPDF, inputs: list[dict]) -> None:
        """Render the required-inputs as a two or three-column table."""
        has_defaults = any(row["default"] for row in inputs)

        if has_defaults:
            col_w = [CONTENT_W * 0.30, CONTENT_W * 0.45, CONTENT_W * 0.25]
            headers = ["Campo", "Descripcion", "Valor por defecto"]
        else:
            col_w = [CONTENT_W * 0.32, CONTENT_W * 0.68]
            headers = ["Campo", "Descripcion"]

        line_h = 5.0
        font_size = 8.5

        # Header row
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.set_text_color(*COLOR_WHITE)
        pdf.set_font("Helvetica", "B", font_size)
        pdf.set_draw_color(*COLOR_LINE)
        pdf.set_line_width(0.2)

        x0, y0 = MARGIN_L, pdf.get_y()
        for j, (h, w) in enumerate(zip(headers, col_w)):
            pdf.set_xy(x0 + sum(col_w[:j]), y0)
            pdf.multi_cell(w, line_h, _safe(h), border=1, fill=True,
                           align="C", new_x="RIGHT", new_y="TOP", max_line_height=line_h)
        pdf.set_xy(x0, y0 + line_h + 1)

        # Body rows
        pdf.set_font("Helvetica", "", font_size)
        pdf.set_text_color(*COLOR_SECONDARY)
        for idx, row in enumerate(inputs):
            fill = COLOR_TABLE_ALT if idx % 2 == 0 else COLOR_WHITE
            pdf.set_fill_color(*fill)

            if has_defaults:
                cells = [row["field"], row["description"], row["default"]]
            else:
                cells = [row["field"], row["description"]]

            # Compute row height
            max_lines = 1
            for cell_txt, w in zip(cells, col_w):
                n = _count_lines(pdf, cell_txt, w, size=font_size)
                max_lines = max(max_lines, n)
            row_h = max_lines * line_h + 1

            if pdf.get_y() + row_h > pdf.h - pdf.b_margin:
                pdf.add_page()
                # Re-draw header after page break
                self._draw_inputs_table(pdf, inputs[idx:])
                return

            x0, y0 = MARGIN_L, pdf.get_y()
            for j, (cell_txt, w) in enumerate(zip(cells, col_w)):
                pdf.set_xy(x0 + sum(col_w[:j]), y0)
                pdf.set_font("Helvetica", "B" if j == 0 else "", font_size)
                pdf.multi_cell(w, line_h, _safe(cell_txt), border=1, fill=True,
                               new_x="RIGHT", new_y="TOP", max_line_height=line_h)
            pdf.set_xy(x0, y0 + row_h)

    def _draw_footer_note(self, pdf: FPDF) -> None:
        pdf.ln(3)
        pdf.set_x(MARGIN_L)
        pdf.set_fill_color(*COLOR_ACCENT)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.multi_cell(CONTENT_W, 6, _safe("  Nota sobre busqueda web automatica"), fill=True)
        pdf.set_x(MARGIN_L)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*COLOR_SECONDARY)
        note = (
            "Todas las habilidades incluyen un mecanismo de busqueda web automatica. "
            "Si el PDF de la empresa no contiene alguno de los campos listados, el agente "
            "realizara una busqueda en internet para completar la informacion faltante. "
            "Sin embargo, los datos encontrados en internet son menos precisos que los "
            "proporcionados directamente en el documento corporativo."
        )
        pdf.multi_cell(CONTENT_W, 5, _safe(note))

    def _apply_footer(self, pdf: FPDF) -> None:
        """Stamp page-number footer on every page."""
        total = len(pdf.pages)
        for page_num in range(1, total + 1):
            pdf.page = page_num
            pdf.set_y(-14)
            pdf.set_x(MARGIN_L)
            pdf.set_draw_color(*COLOR_LINE)
            pdf.set_line_width(0.3)
            pdf.line(MARGIN_L, pdf.get_y(), PAGE_W - MARGIN_R, pdf.get_y())
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(CONTENT_W / 2, 6, _safe("Sistema de Agentes Autonomos"), align="L")
            pdf.cell(CONTENT_W / 2, 6, _safe(f"Pagina {page_num} de {total}"), align="R")
        pdf.page = total   # leave cursor on last page
