"""
main.py — Entry point for the Autonomous Agent System.

Scheduling:
  - Every 4 hours : generate/refresh PDF reports for all known companies.
  - Once a month  : full orchestration cycle (skills reloaded, all companies reprocessed).

Both jobs execute the same pipeline; the monthly job is an explicit full-refresh marker.
On startup the pipeline runs immediately before the scheduler begins.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

load_dotenv()

from src.agents.central_agent import CentralAgent
from src.utils.pdf_writer import PDFReportWriter
from src.utils.instructions_writer import InstructionsWriter

# ------------------------------------------------------------------ #
#  Logging                                                            #
# ------------------------------------------------------------------ #
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "agent_system.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Paths (all relative to this file's directory)                      #
# ------------------------------------------------------------------ #
PROMPTS_DIR   = BASE_DIR / "src" / "prompts"
EMPRESAS_DIR  = BASE_DIR / "data" / "empresas"
LISTAS_DIR    = BASE_DIR / "data" / "listas"    # PDFs with company name lists
OUTPUTS_DIR   = BASE_DIR / "outputs"


# ------------------------------------------------------------------ #
#  Core pipeline                                                      #
# ------------------------------------------------------------------ #
def run_pipeline(label: str = "manual") -> None:
    """
    Run the full processing pipeline:
      1. Load skills from src/prompts/*.md
      2. Read each PDF in data/empresas/
      3. Apply every skill to every company
      4. Save one PDF report per (company, skill) pair inside outputs/{company}/
    """
    start = datetime.now()
    logger.info("=" * 60)
    logger.info("Pipeline triggered  [%s]  %s", label, start.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    agent = CentralAgent(
        prompts_dir=PROMPTS_DIR,
        empresas_dir=EMPRESAS_DIR,
        outputs_dir=OUTPUTS_DIR,
        listas_dir=LISTAS_DIR,
    )
    writer = PDFReportWriter()
    reports_saved = 0

    for company_name, results in agent.run_cycle():
        company_dir = OUTPUTS_DIR / company_name
        company_dir.mkdir(parents=True, exist_ok=True)

        for skill_name, content in results.items():
            timestamp = start.strftime("%Y%m%d_%H%M%S")
            filename = f"{skill_name}_{timestamp}.pdf"
            report_path = company_dir / filename

            writer.generate_report(
                output_path=report_path,
                company_name=company_name,
                skill_name=skill_name,
                content=content,
            )
            reports_saved += 1

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(
        "Pipeline finished — %d report(s) saved in %.1f s",
        reports_saved,
        elapsed,
    )


# ------------------------------------------------------------------ #
#  Scheduler jobs                                                     #
# ------------------------------------------------------------------ #
def job_4h() -> None:
    run_pipeline(label="4h-schedule")


def job_monthly() -> None:
    run_pipeline(label="monthly-full-cycle")


# ------------------------------------------------------------------ #
#  Main                                                               #
# ------------------------------------------------------------------ #
def generate_instructions() -> None:
    """
    Generate the reference PDF that explains what each skill needs.
    Saved to outputs/instructions/ on every startup.
    """
    instructions_dir = OUTPUTS_DIR / "instructions"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = instructions_dir / f"guia_informacion_requerida_{ts}.pdf"

    logger.info("Generating instructions PDF → %s", output_path)
    try:
        InstructionsWriter().generate(
            output_path=output_path,
            prompts_dir=PROMPTS_DIR,
        )
    except Exception as exc:
        logger.error("Failed to generate instructions PDF: %s", exc)


if __name__ == "__main__":
    # Ensure required directories exist
    for directory in (PROMPTS_DIR, EMPRESAS_DIR, LISTAS_DIR, OUTPUTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    # Generate instructions PDF before starting the pipeline
    generate_instructions()

    # Run immediately on startup — intervals are anchored to when this finishes
    run_pipeline(label="startup")
    cycle_anchor = datetime.now()

    # Configure scheduler
    scheduler = BlockingScheduler(timezone="America/Mexico_City")

    scheduler.add_job(
        job_4h,
        trigger=IntervalTrigger(hours=4, start_date=cycle_anchor, timezone="America/Mexico_City"),
        id="report_4h",
        name="Generate reports every 4 hours",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        job_monthly,
        trigger=CronTrigger(day=1, hour=0, minute=0, timezone="America/Mexico_City"),
        id="full_cycle_monthly",
        name="Full orchestration cycle every month",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )

    logger.info("Scheduler started — reports every 4 h, full cycle every month.")
    logger.info("Company documents : %s", EMPRESAS_DIR)
    logger.info("Company name lists: %s  (one name per line)", LISTAS_DIR)
    logger.info("Skill prompts     : %s  (*.md files)", PROMPTS_DIR)
    logger.info("Reports saved to  : %s", OUTPUTS_DIR)
    logger.info("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user.")
