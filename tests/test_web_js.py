"""Red de seguridad del frontend: sintaxis JS y consistencia de registros."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).parent.parent / "visual_options" / "stream" / "web"
node = shutil.which("node")


@pytest.mark.skipif(node is None, reason="node no disponible")
@pytest.mark.parametrize("js_file", sorted(WEB.glob("*.js")), ids=lambda p: p.name)
def test_js_syntax(js_file):
    result = subprocess.run([node, "--check", str(js_file)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"{js_file.name}: {result.stderr}"


def test_views_registered_consistently():
    app_js = (WEB / "app.js").read_text()
    index_html = (WEB / "index.html").read_text()

    views_block = re.search(r"const VIEWS = \{(.*?)\};", app_js, re.S).group(1)
    view_ids = set(re.findall(r"(\w+):\s*\w+View", views_block))
    assert len(view_ids) >= 20

    titles_block = re.search(r"const VIEW_TITLES = \{(.*?)\};", app_js, re.S).group(1)
    title_ids = set(re.findall(r"(\w+):\s*\"", titles_block))
    assert view_ids == title_ids, f"VIEWS vs VIEW_TITLES: {view_ids ^ title_ids}"

    nav_block = re.search(r"const NAV_GROUPS = \[(.*?)\];\n", app_js, re.S).group(1)
    nav_ids = set(re.findall(r"\"(\w+)\"", nav_block)) - {
        "Mercado", "Precio", "Opciones", "Análisis", "Herramientas"}
    assert nav_ids <= view_ids, f"vistas en NAV sin registrar: {nav_ids - view_ids}"

    scripts = set(re.findall(r'/static/(\w+)\.js', index_html))
    js_files = {p.stem for p in WEB.glob("*.js")}
    assert scripts == js_files, f"scripts vs archivos: {scripts ^ js_files}"


def test_home_cards_point_to_registered_views():
    app_js = (WEB / "app.js").read_text()
    home_js = (WEB / "home.js").read_text()
    views_block = re.search(r"const VIEWS = \{(.*?)\};", app_js, re.S).group(1)
    view_ids = set(re.findall(r"(\w+):\s*\w+View", views_block))
    card_views = set(re.findall(r'view:\s*"(\w+)"', home_js))
    assert card_views <= view_ids, f"tarjetas sin vista: {card_views - view_ids}"
