"""
Skill Agent — wraps a single .md skill prompt and calls the OpenAI API.

Each SkillAgent is responsible for one analysis type (e.g. "analisis_financiero").
It receives the company text extracted from a PDF and returns the analysis as a string.
Web search is enabled so the model can look up missing company data automatically.
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

        Uses the Responses API with web_search_preview so the model can
        search for missing company data when the PDF is incomplete.

        Args:
            company_text: Text extracted from the company PDF.
            company_name: Company identifier (used in the user prompt).

        Returns:
            The model's analysis as a plain string.
        """
        user_message = (
            f"Nombre de archivo (solo referencia): **{company_name}**\n\n"
            f"Información extraída del documento corporativo:\n\n"
            f"{company_text}\n\n"
            "PASO PREVIO OBLIGATORIO: Identifica el nombre real de la empresa o marca "
            "a partir del documento. Si no aparece con claridad en el texto, usa el nombre "
            "de archivo como aproximación. Usa ese nombre real en todo el análisis y en "
            "cualquier búsqueda web que realices para completar información faltante.\n\n"
            "Realiza el análisis completo según las instrucciones del sistema."
        )

        logger.debug(
            "SkillAgent '%s' calling model '%s' for '%s'",
            self.skill_name,
            self._model,
            company_name,
        )

        payload = dict(
            model=self._model,
            max_output_tokens=4096,
            input=[
                {"role": "system", "content": self.skill_prompt},
                {"role": "user", "content": user_message},
            ],
        )

        try:
            response = self._client.responses.create(
                **payload,
                tools=[{"type": "web_search_preview"}],
            )
            return response.output_text

        except APIError as exc:
            if exc.status_code in (400, 422):
                logger.warning(
                    "web_search_preview not supported by model '%s' — retrying without it. (%s)",
                    self._model,
                    exc,
                )
                try:
                    response = self._client.responses.create(**payload)
                    return response.output_text
                except APIError as retry_exc:
                    logger.error(
                        "API error in skill '%s' for '%s' (fallback): %s",
                        self.skill_name,
                        company_name,
                        retry_exc,
                    )
                    return f"[ERROR] No se pudo completar el analisis '{self.skill_name}': {retry_exc}"

            logger.error(
                "API error in skill '%s' for '%s': %s",
                self.skill_name,
                company_name,
                exc,
            )
            return f"[ERROR] No se pudo completar el analisis '{self.skill_name}': {exc}"
