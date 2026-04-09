"""
Central Agent — orchestrates the entire pipeline.

Responsibilities:
  1. Dynamically load every .md file in src/prompts/ as a named Skill.
  2. Discover PDF files in data/empresas/ (full company documents).
  3. Discover PDF files in data/listas/ (name-list PDFs — one company per line).
  4. For each company, instantiate a SkillAgent per skill and execute it.
  5. Yield (company_name, {skill_name: result_text}) pairs for the caller to persist.
"""
import logging
from pathlib import Path
from typing import Generator

from src.agents.skill_agent import SkillAgent
from src.utils.pdf_reader import PDFReader

logger = logging.getLogger(__name__)


class CentralAgent:
    """
    Top-level orchestrator.

    Args:
        prompts_dir: Directory containing .md skill definitions.
        empresas_dir: Directory containing full company PDF documents.
        outputs_dir: Root output directory (used for logging only here).
        listas_dir: Directory containing name-list PDFs (one company name per line).
                    When provided, each line in those PDFs is treated as a separate
                    company and all skills are run using web search as the data source.
    """

    def __init__(
        self,
        prompts_dir: str | Path,
        empresas_dir: str | Path,
        outputs_dir: str | Path,
        listas_dir: str | Path | None = None,
    ) -> None:
        self.prompts_dir = Path(prompts_dir)
        self.empresas_dir = Path(empresas_dir)
        self.outputs_dir = Path(outputs_dir)
        self.listas_dir = Path(listas_dir) if listas_dir else None
        self._pdf_reader = PDFReader()
        self._skills: dict[str, str] = {}
        self._agents: dict[str, SkillAgent] = {}

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def load_skills(self) -> None:
        """Reload all .md files from the prompts directory."""
        self._skills.clear()
        self._agents.clear()

        if not self.prompts_dir.exists():
            logger.warning("Prompts directory not found: %s", self.prompts_dir)
            return

        md_files = sorted(self.prompts_dir.glob("*.md"))
        if not md_files:
            logger.warning("No .md skill files found in %s", self.prompts_dir)
            return

        for md_file in md_files:
            skill_name = md_file.stem
            prompt_text = md_file.read_text(encoding="utf-8")
            self._skills[skill_name] = prompt_text
            self._agents[skill_name] = SkillAgent(skill_name, prompt_text)
            logger.info("Skill loaded: '%s'  (%d chars)", skill_name, len(prompt_text))

    def run_cycle(
        self,
    ) -> Generator[tuple[str, dict[str, str]], None, None]:
        """
        Execute the full processing cycle.

        Processes two sources:
          - ``empresas_dir``: full company PDF documents (text extracted and sent as context).
          - ``listas_dir``:  name-list PDFs — one company name per line, skills rely on
                             web search to gather the information.

        Yields:
            (company_name, results_dict) where results_dict maps skill_name -> analysis text.
        """
        logger.info("=== CentralAgent cycle started ===")
        self.load_skills()

        if not self._agents:
            logger.error("No skills available — aborting cycle.")
            return

        # ── 1. Full-document PDFs ─────────────────────────────────────────
        pdf_files = sorted(self.empresas_dir.glob("*.pdf"))
        list_pdfs = (
            sorted(self.listas_dir.glob("*.pdf"))
            if self.listas_dir and self.listas_dir.exists()
            else []
        )

        if not pdf_files and not list_pdfs:
            logger.warning(
                "No PDF files found in '%s' or '%s'.",
                self.empresas_dir,
                self.listas_dir,
            )
            return

        logger.info(
            "Found %d company PDF(s), %d name-list PDF(s), and %d skill(s).",
            len(pdf_files),
            len(list_pdfs),
            len(self._agents),
        )

        for pdf_path in pdf_files:
            company_name = pdf_path.stem
            logger.info("--- Processing company document: %s ---", company_name)

            try:
                company_text = self._pdf_reader.extract_text(pdf_path)
            except Exception as exc:
                logger.error("Could not read '%s': %s — skipping.", pdf_path.name, exc)
                continue

            results: dict[str, str] = {}
            for skill_name, agent in self._agents.items():
                logger.info("  Running skill '%s' ...", skill_name)
                results[skill_name] = agent.execute(company_text, company_name)

            yield company_name, results

        # ── 2. Name-list PDFs ─────────────────────────────────────────────
        for lista_path in list_pdfs:
            logger.info("--- Reading name list: %s ---", lista_path.name)

            try:
                company_names = self._extract_company_names(lista_path)
            except Exception as exc:
                logger.error("Could not read name list '%s': %s — skipping.", lista_path.name, exc)
                continue

            if not company_names:
                logger.warning("No company names found in '%s' — skipping.", lista_path.name)
                continue

            logger.info("  Found %d company name(s) in list.", len(company_names))

            for company_name in company_names:
                logger.info("--- Processing (from list): %s ---", company_name)

                # Minimal context — agent will use web search to find the data
                company_text = (
                    f"Empresa: {company_name}\n\n"
                    "No se dispone de un documento corporativo. "
                    "Usa búsqueda web para obtener toda la información necesaria."
                )

                results: dict[str, str] = {}
                for skill_name, agent in self._agents.items():
                    logger.info("  Running skill '%s' ...", skill_name)
                    results[skill_name] = agent.execute(company_text, company_name)

                yield company_name, results

        logger.info("=== CentralAgent cycle finished ===")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_company_names(self, pdf_path: Path) -> list[str]:
        """
        Extract company names from a name-list PDF.

        Each non-empty line in the PDF is treated as a separate company name.
        Lines that start with ``#`` or ``-`` are treated as comments/headers
        and are ignored.

        Args:
            pdf_path: Path to the name-list PDF.

        Returns:
            List of cleaned company name strings.
        """
        raw_text = self._pdf_reader.extract_text(pdf_path)
        names: list[str] = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Skip comment / header lines
            if stripped.startswith("#") or stripped.startswith("-"):
                continue
            names.append(stripped)
        return names
