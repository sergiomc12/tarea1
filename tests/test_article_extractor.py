"""Tests de extracción de artículos."""

from datetime import datetime, timezone

from scraper_agent.parser.article_extractor import (
    build_content_blocks,
    extract_article,
    generate_article_id,
    _find_article_root,
)

ARTICLE_HTML = """
<html><head>
<meta property="article:published_time" content="2026-07-04T18:19:00Z"/>
<meta property="og:title" content="Titulo principal"/>
<meta property="og:image" content="https://gestion.pe/img/cover.jpg"/>
</head><body><article>
<h1>Titulo principal</h1>
<p>Primer parrafo del articulo.</p>
<p>Segundo parrafo con mas detalle.</p>
<blockquote>Una cita relevante.</blockquote>
<a href="https://gestion.pe/otra-nota">Lea tambien otra nota</a>
</article></body></html>
"""


def test_generate_article_id_deterministic():
    a = generate_article_id("https://gestion.pe/nota/", "2026-07-04T18:19:00Z")
    b = generate_article_id("https://gestion.pe/nota/", "2026-07-04T18:19:00Z")
    assert a == b
    assert a.startswith("gestion-")


INLINE_LINK_HTML = """
<html><body><article>
<p>Beijing, China.- <ins><a href="https://gestion.pe/economia/otra-nota/">Mientras nuevos productos agrícolas buscan abrirse paso hacia China, otros ya se han consolidado y concentran la mayor parte de los envios del sector.</a></ins> Peru registra una lista de agroexportaciones.</p>
</article></body></html>
"""

GESTION_SIDEBAR_HTML = """
<html><body>
<aside>
<article class="most-read-by-site__item"><h2>PLUS G Inversion china llega a Las Malvinas</h2></article>
</aside>
<div class="story-contents">
<h1>Chocaron tu auto en un estacionamiento</h1>
<p>Primer parrafo real del articulo sobre estacionamientos.</p>
<p>Segundo parrafo con mas detalle legal.</p>
</div>
</body></html>
"""


def test_build_content_blocks_order():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(ARTICLE_HTML, "lxml")
    blocks = build_content_blocks(soup.find("article"), base_url="https://gestion.pe/nota/")
    assert blocks[0]["type"] == "heading"
    assert blocks[0]["order"] == 0
    assert blocks[1]["type"] == "paragraph"


def test_paragraph_runs_inline_link():
    from bs4 import BeautifulSoup

    from scraper_agent.storage.schema_validator import validate_article

    soup = BeautifulSoup(INLINE_LINK_HTML, "lxml")
    blocks = build_content_blocks(soup.find("article"), base_url="https://gestion.pe/economia/nota/")
    para_block = next(b for b in blocks if b["type"] == "paragraph")
    assert "runs" in para_block
    link_runs = [r for r in para_block["runs"] if r["kind"] == "link"]
    assert len(link_runs) == 1
    assert link_runs[0]["url"].endswith("/economia/otra-nota")
    assert "".join(r["text"] for r in para_block["runs"]) == para_block["text"]

    minimal_article = {
        "article_id": "gestion-testruns",
        "url": "https://gestion.pe/economia/nota/",
        "canonical_url": "https://gestion.pe/economia/nota/",
        "amp_url": None,
        "fetch_info": {
            "status_code": 200,
            "fetched_at": "2026-07-05T00:00:00Z",
            "response_time_ms": None,
            "final_url_after_redirects": "https://gestion.pe/economia/nota/",
            "html_hash": "sha256:" + "b" * 64,
            "content_length_bytes": 500,
        },
        "identification": {
            "site_name": "gestion.pe",
            "section": "Economia",
            "subsection": None,
            "breadcrumbs": [],
            "is_premium": False,
            "premium_label": None,
        },
        "headline": {"title": "Test", "subtitle": None, "kicker": None, "meta_title": None, "og_title": None},
        "dates": {
            "published_at": "2026-07-05T00:00:00Z",
            "updated_at": None,
            "published_at_raw": None,
            "timezone": "America/Lima",
        },
        "content_blocks": [para_block],
        "access": {"is_paywalled": False, "paywall_type": None, "requires_login": False},
    }
    assert validate_article(minimal_article) == []


def test_find_article_root_ignores_sidebar_widget():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(GESTION_SIDEBAR_HTML, "lxml")
    blocks = build_content_blocks(_find_article_root(soup), base_url="https://gestion.pe/economia/nota/")
    texts = [b["text"] for b in blocks]
    assert any("estacionamiento" in t.lower() for t in texts)
    assert not any("malvinas" in t.lower() for t in texts)
    assert sum(1 for b in blocks if b["type"] == "paragraph") >= 2


GESTION_LEA_TAMBIEN_HTML = """
<html><body><div class="story-contents">
<p>Intro del articulo.</p>
<blockquote class="story-contents__blockquote"><b>LEA TAMBIÉN: </b><a href="https://gestion.pe/economia/otra/">Titulo de enlace relacionado</a></blockquote>
<p class="story-contents__about-author-bio">Bio del autor que no debe aparecer.</p>
</div></body></html>
"""

GESTION_HEADER_HTML = """
<html><body>
<ul class="sht__list"><li><a href="https://gestion.pe/economia/enlace-bajo-titular/">Puerto de Chancay cumplio su primer ano</a></li></ul>
<div class="story-contents"><p>Cuerpo del articulo principal.</p></div>
</body></html>
"""


def test_read_also_blockquote_becomes_related_link():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(GESTION_LEA_TAMBIEN_HTML, "lxml")
    blocks = build_content_blocks(soup.select_one(".story-contents"), base_url="https://gestion.pe/nota/")
    related = [b for b in blocks if b["type"] == "related_link"]
    assert len(related) == 1
    assert related[0]["url"].endswith("/otra")
    assert "Bio del autor" not in " ".join(b.get("text", "") for b in blocks)


def test_header_related_links_and_deck():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(GESTION_HEADER_HTML, "lxml")
    blocks = build_content_blocks(
        soup.select_one(".story-contents"),
        base_url="https://gestion.pe/nota/",
        soup=soup,
        subtitle="Bajada del articulo bajo el titular.",
    )
    assert blocks[0]["type"] == "paragraph"
    assert "Bajada del articulo" in blocks[0]["text"]
    assert blocks[1]["type"] == "related_link"
    assert "Chancay" in blocks[1]["text"]


FULL_LINK_PARAGRAPH_HTML = """
<html><body><div class="story-contents">
<p><a href="https://gestion.pe/economia/otra-nota/">Todo este parrafo es un solo enlace de recirculacion sin mezcla de texto.</a></p>
</div></body></html>
"""


def test_whole_paragraph_link_omits_runs():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(FULL_LINK_PARAGRAPH_HTML, "lxml")
    blocks = build_content_blocks(soup.select_one(".story-contents"), base_url="https://gestion.pe/nota/")
    para = blocks[0]
    assert para["type"] == "paragraph"
    assert "Todo este parrafo" in para["text"]
    assert "runs" not in para


def test_extract_article_structure():
    art = extract_article(
        "https://gestion.pe/economia/nota-test/",
        ARTICLE_HTML,
        200,
        datetime.now(timezone.utc),
    )
    assert art is not None
    assert art["headline"]["title"] == "Titulo principal"
    assert len(art["content_blocks"]) >= 3
    assert art["dates"]["published_at"] is not None
    assert art["media"]["cover_image"]["url"] == "https://gestion.pe/img/cover.jpg"


JSONLD_BODY_HTML = """
<html><head>
<meta property="og:title" content="Titulo desde meta"/>
<script type="application/ld+json">
{
  "@type": "NewsArticle",
  "headline": "Titulo JSON-LD",
  "datePublished": "2026-07-04T18:00:00Z",
  "articleBody": "Primer parrafo largo del cuerpo del articulo extraido desde JSON-LD con suficiente texto para superar el minimo requerido de trescientos caracteres y validar el fallback cuando el DOM esta vacio.\\n\\nSegundo parrafo igualmente largo con detalles adicionales sobre la noticia publicada en el medio peruano y mas contexto editorial para completar el umbral minimo de extraccion desde metadatos estructurados."
}
</script>
</head><body><div id="app"></div></body></html>
"""


def test_extract_article_falls_back_to_jsonld_article_body():
    art = extract_article(
        "https://elcomercio.pe/economia/nota-jsonld/",
        JSONLD_BODY_HTML,
        200,
        datetime.now(timezone.utc),
    )
    assert art is not None
    paragraphs = [b for b in art["content_blocks"] if b["type"] == "paragraph"]
    assert len(paragraphs) >= 2
    assert "JSON-LD" in paragraphs[0]["text"] or "JSON-LD" in " ".join(p["text"] for p in paragraphs)
