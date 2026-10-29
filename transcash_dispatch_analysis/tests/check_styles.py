"""Compile the module's SCSS with the LibSass binding installed with Odoo.

Run using the Python environment that runs Odoo:
    python3 transcash_dispatch_analysis/tests/check_styles.py
"""
from pathlib import Path
import ast
import json


def main():
    import sass

    module = Path(__file__).resolve().parents[1]
    manifest = ast.literal_eval((module / "__manifest__.py").read_text())
    assets = manifest["assets"]["web.assets_backend"]
    sources = []
    compiled = []
    for asset in assets:
        if not asset.endswith(".scss"):
            continue
        path = module.parent / asset
        content = path.read_text()
        css = sass.compile(string=content, output_style="expanded")
        if not css.strip():
            raise ValueError("El estilo está vacío: %s" % path.name)
        sources.append(content)
        compiled.append({"asset": asset, "compiled_bytes": len(css.encode())})
    if not sources:
        raise ValueError("No se encontraron estilos SCSS en el paquete.")
    combined = sass.compile(string="\n".join(sources), output_style="compressed")
    print(json.dumps({"python_binding": sass.__version__,
        "libsass": getattr(sass, "libsass_version", "unknown"),
        "styles": compiled, "combined_compiled_bytes": len(combined.encode())}, indent=2))


if __name__ == "__main__":
    main()
