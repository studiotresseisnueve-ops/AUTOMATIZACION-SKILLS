"""
Central Agent — orchestrates the entire pipeline.

Responsibilities:
  1. Dynamically load every .md file in src/prompts/ as a named Skill.
  2. Discover PDF files in data/empresas/.
  3. For each PDF, instantiate a SkillAgent per skill and execute it.
  4. Yield (company_name, {skill_name: result_text}) pairs for the caller to persist.
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
        empresas_dir: Directory containing company PDF files.
        outputs_dir: Root output directory (used for logging only here).
    """

    def __init__(
        self,
        prompts_dir: str | Path,
        empresas_dir: str | Path,
        outputs_dir: str | Path,
    ) -> None:
        self.prompts_dir = Path(prompts_dir)
        self.empresas_dir = Path(empresas_dir)
        self.outputs_dir = Path(outputs_dir)
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

        Yields:
            (company_name, results_dict) where results_dict maps
            skill_name -> analysis text.
        """
        logger.info("=== CentralAgent cycle started ===")
        self.load_skills()

        if not self._agents:
            logger.error("No skills available — aborting cycle.")
            return

        pdf_files = sorted(self.empresas_dir.glob("*.pdf"))
        if not pdf_files:
            logger.warning("No PDF files found in %s", self.empresas_dir)
            return

        logger.info(
            "Found %d company PDF(s) and %d skill(s).",
            len(pdf_files),
            len(self._agents),
        )

        for pdf_path in pdf_files:
            company_name = pdf_path.stem
            logger.info("--- Processing: %s ---", company_name)

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

        logger.info("=== CentralAgent cycle finished ===")
