"""Anti-detección: user-agents, delays."""

from scraper_agent.anti_detection.delays import random_delay
from scraper_agent.anti_detection.user_agents import pick_user_agent

__all__ = ["pick_user_agent", "random_delay"]
