"""Hook opcional para servicio de CAPTCHA (responsabilidad del operador)."""

from scraper_agent.utils.logger import get_logger

logger = get_logger(__name__)


def solve_captcha(image_bytes: bytes, provider: str | None = None) -> str | None:
    """Placeholder: integrar 2Captcha u otro servicio autorizado por el usuario."""
    logger.warning("captcha_solver_not_configured", provider=provider)
    return None
