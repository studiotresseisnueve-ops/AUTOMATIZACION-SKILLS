"""
Skill Agent — wraps a single .md skill prompt and calls the OpenAI API.

Each SkillAgent is responsible for one analysis type (e.g. "analisis_financiero").
It receives the company text extracted from a PDF and returns the analysis as a string.
"""
import logging
import os

from openai import OpenAI, APIError

logger = logging.getLogger(__name__)


class SkillAgent:
    """
    Specialised agent that applies one skill to a company document.

    Args:
        skill_name: Human-readable name derived from the .md file stem.
        skill_prompt: Full content of the .md skill file (used as system prompt).
    """

    def __init__(self, skill_name: str, skill_prompt: str) -> None:
        self.skill_name = skill_name
        self.skill_prompt = skill_prompt
        self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o")

    # ------------------------------------------------------------------ #

    def execute(self, company_text: str, company_name: str) -> str:
        """
        Run the skill against a company document.

        Args:
            company_text: Text extracted from the company PDF.
            company_name: Company identifier (used in the user prompt).

        Returns:
            The model's analysis as a plain string.
        """
        user_message = (
            f"Empresa analizada: **{company_name}**\n\n"
            f"Información extraída del documento corporativo:\n\n"
            f"{company_text}\n\n"
            "Por favor, realiza el análisis completo según las instrucciones del sistema."
        )

        logger.debug(
            "SkillAgent '%s' calling model '%s' for '%s'",
            self.skill_name,
            self._model,
            company_name,
        )

        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": self.skill_prompt},
                    {"role": "user", "content": user_message},
                ],
                stream=True,
            )

            chunks = []
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta is not None:
                    chunks.append(delta)

            return "".join(chunks)

        except APIError as exc:
            logger.error(
                "API error in skill '%s' for '%s': %s",
                self.skill_name,
                company_name,
                exc,
            )
            return f"[ERROR] No se pudo completar el analisis '{self.skill_name}': {exc}"
