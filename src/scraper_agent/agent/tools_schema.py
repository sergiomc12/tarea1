"""Definiciones de tools para el agente orquestador (OpenAI/DeepSeek format)."""

from __future__ import annotations

from scraper_agent.agent.llm_models import ToolDefinition, ToolFunctionSchema
from scraper_agent.security_env.tool_runner import load_tool_catalog


def _security_tool_ids() -> list[str]:
    return sorted(load_tool_catalog().keys())


def build_agent_tools() -> list[ToolDefinition]:
    """Tools que el LLM puede invocar vía function calling."""
    security_ids = _security_tool_ids()
    return [
        ToolDefinition(
            function=ToolFunctionSchema(
                name="run_site_crawl",
                description=(
                    "Ejecuta el crawler de noticias sobre un medio configurado "
                    "(config/sites/). No requiere authorized_targets."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "config_path": {
                            "type": "string",
                            "description": "Ruta YAML del sitio, ej. config/gestion_pe.yaml",
                        },
                        "from_date": {
                            "type": "string",
                            "description": "ISO 8601 opcional",
                        },
                        "to_date": {
                            "type": "string",
                            "description": "ISO 8601 opcional",
                        },
                    },
                    "required": ["config_path"],
                    "additionalProperties": False,
                },
            )
        ),
        ToolDefinition(
            function=ToolFunctionSchema(
                name="search_crawl_output",
                description=(
                    "Busca por objetivo profesional en un JSON de crawl existente "
                    "sin re-crawlear (equivalente a scraper-agent search --input)."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "input_json": {
                            "type": "string",
                            "description": "Ruta al JSON de salida del crawl",
                        },
                        "target_file": {
                            "type": "string",
                            "description": "Ruta YAML en config/targets/",
                        },
                    },
                    "required": ["input_json", "target_file"],
                    "additionalProperties": False,
                },
            )
        ),
        ToolDefinition(
            function=ToolFunctionSchema(
                name="list_security_tools",
                description="Lista herramientas Kali disponibles en el catálogo cerrado.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
        ),
        ToolDefinition(
            function=ToolFunctionSchema(
                name="run_security_tool",
                description=(
                    "Ejecuta una herramienta del catálogo security_env contra un host "
                    "autorizado en config/authorized_targets.yaml."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "tool_id": {
                            "type": "string",
                            "enum": security_ids,
                            "description": "ID en tool_catalog.yaml",
                        },
                        "host": {
                            "type": "string",
                            "description": "Dominio o IP autorizado",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "ID de sesión Kali (workspace aislado)",
                        },
                    },
                    "required": ["tool_id", "host"],
                    "additionalProperties": False,
                },
            )
        ),
    ]


def tools_as_api_payload(tools: list[ToolDefinition] | None = None) -> list[dict]:
    """Serializa tools para el body de chat/completions."""
    source = tools if tools is not None else build_agent_tools()
    return [tool.model_dump(exclude_none=True) for tool in source]
