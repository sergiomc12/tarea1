"""Tests de extracción de authorship y taxonomy."""

from datetime import datetime, timezone

from scraper_agent.parser.article_extractor import (
    _extract_authors,
    _extract_taxonomy,
    extract_article,
)
from bs4 import BeautifulSoup


GESTION_AUTHOR_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@type": "NewsArticle",
  "author": {
    "@type": "Person",
    "name": "Gerardo Rosales Diaz",
    "url": "https://gestion.pe/autor/gerardo-rosales"
  },
  "articleSection": "Economía",
  "keywords": ["gratificación", "trabajadores"]
}
</script>
<meta name="author" content="Redacción Gestión"/>
</head><body>
<div class="story-contents">
<a class="story-body-author__name" href="https://gestion.pe/autor/gerardo-rosales">Gerardo Rosales Diaz</a>
</div>
</body></html>
"""

OJO_BYLINE_HTML = """
<html><head>
<meta property="article:section" content="Mujer"/>
<meta property="article:tag" content="Lima Teje"/>
<meta property="article:tag" content="textiles"/>
</head><body>
<p class="author-name">Por María López</p>
</body></html>
"""

BREADCRUMB_TAXONOMY_HTML = """
<html><head>
<meta property="article:section" content="Curiosidades"/>
</head><body>
<nav class="breadcrumb">
  <a href="/">Inicio</a>
  <a href="/tecnologia">Tecnología</a>
  <a href="/curiosidades">Curiosidades</a>
</nav>
<div class="tags"><a href="/tag/whatsapp">WhatsApp</a></div>
</body></html>
"""


def test_extract_authors_from_json_ld_and_profile_link():
    soup = BeautifulSoup(GESTION_AUTHOR_HTML, "lxml")
    ld = {"author": {"@type": "Person", "name": "Gerardo Rosales Diaz", "url": "https://gestion.pe/autor/gerardo-rosales"}}
    authorship = _extract_authors(soup, "https://gestion.pe/economia/nota/", ld)
    assert authorship["authors"]
    author = authorship["authors"][0]
    assert author["name"] == "Gerardo Rosales Diaz"
    assert author["author_url"] == "https://gestion.pe/autor/gerardo-rosales"
    assert authorship["agency_source"] == "Redacción Gestión"


def test_extract_authors_from_byline_text():
    soup = BeautifulSoup(OJO_BYLINE_HTML, "lxml")
    authorship = _extract_authors(soup, "https://ojo.pe/nota/", {})
    assert len(authorship["authors"]) == 1
    assert authorship["authors"][0]["name"] == "María López"
    assert authorship["authors"][0]["byline_raw"] == "Por María López"


def test_extract_taxonomy_tags_and_categories():
    soup = BeautifulSoup(OJO_BYLINE_HTML, "lxml")
    identification = {"section": "Mujer", "breadcrumbs": []}
    taxonomy = _extract_taxonomy(soup, "https://ojo.pe/mujer/nota/", {}, identification)
    assert taxonomy["primary_category"] == "Mujer"
    assert "Lima Teje" in taxonomy["tags"]
    assert "textiles" in taxonomy["tags"]


def test_extract_taxonomy_breadcrumbs_and_tag_links():
    soup = BeautifulSoup(BREADCRUMB_TAXONOMY_HTML, "lxml")
    identification = {
        "section": "Curiosidades",
        "breadcrumbs": ["Inicio", "Tecnología", "Curiosidades"],
    }
    taxonomy = _extract_taxonomy(soup, "https://ejemplo.pe/curiosidades/nota/", {}, identification)
    assert taxonomy["primary_category"] == "Curiosidades"
    assert "Tecnología" in taxonomy["secondary_categories"]
    assert "WhatsApp" in taxonomy["tags"]


def test_extract_article_includes_enriched_taxonomy():
    html = """
    <html><head>
    <meta property="article:published_time" content="2026-07-04T18:19:00Z"/>
    <meta property="og:title" content="Titulo"/>
    <meta property="article:section" content="Economía"/>
    <meta property="article:tag" content="inflación"/>
    <script type="application/ld+json">
    {"@type":"NewsArticle","author":{"@type":"Person","name":"Ana Pérez","url":"https://gestion.pe/autor/ana"}}
    </script>
    </head><body><div class="story-contents">
    <h1>Titulo</h1><p>Primer parrafo largo del articulo con suficiente texto para validar.</p>
    <p>Segundo parrafo con mas contenido editorial relevante para el lector.</p>
  <p>Tercer parrafo adicional para cumplir bloques sustantivos del extractor.</p>
    </div></body></html>
    """
    article = extract_article(
        "https://gestion.pe/economia/nota/",
        html,
        200,
        datetime.now(timezone.utc),
        site_name="gestion.pe",
    )
    assert article is not None
    assert article["authorship"]["authors"][0]["name"] == "Ana Pérez"
    assert article["taxonomy"]["primary_category"] == "Economía"
    assert "inflación" in article["taxonomy"]["tags"]
