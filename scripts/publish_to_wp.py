#!/usr/bin/env python3
"""
publish_to_wp.py: Convert Jupyter notebooks and README.md files to HTML
and publish them as WordPress pages, without external subprocess calls.
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import nbformat
import requests
from nbconvert import HTMLExporter
from requests.auth import HTTPBasicAuth


class WordPressPublisher:
    def __init__(self):
        self.wp_url = os.getenv("WP_URL")
        self.auth = HTTPBasicAuth(
            os.getenv("WP_USERNAME", ""), os.getenv("WP_PASSWORD", "")
        )
        if not (self.wp_url and self.auth.username and self.auth.password):
            raise RuntimeError("WP_URL, WP_USERNAME, WP_PASSWORD must be set")
        if not self.wp_url.startswith(("http://", "https://")):
            raise RuntimeError("WP_URL must start with http:// or https://")

    def convert_notebook(self, nb_path: Path) -> str:
        """Convert a .ipynb file to HTML using nbconvert’s HTMLExporter[1][2]."""
        nb = nbformat.read(str(nb_path), as_version=4)
        exporter = HTMLExporter()
        html_body, _ = exporter.from_notebook_node(nb)
        return html_body

    def convert_markdown(self, md_path: Path) -> str:
        """Convert a .md file to HTML using markdown library if available,
        else fall back to minimal regex conversion[3]."""
        text = md_path.read_text(encoding="utf-8")
        try:
            import markdown

            return markdown.markdown(text, extensions=["fenced_code", "tables"])
        except ImportError:
            # Fallback: convert headings and paragraphs
            lines = text.splitlines()
            html_lines = []
            for line in lines:
                if line.startswith("# "):
                    html_lines.append(f"<h1>{line[2:].strip()}</h1>")
                elif line.startswith("## "):
                    html_lines.append(f"<h2>{line[3:].strip()}</h2>")
                else:
                    html_lines.append(f"<p>{line.strip()}</p>")
            return "\n".join(html_lines)

    def get_or_create_page(self, title: str, content: str, parent: int = None) -> int:
        """Search for a page by slug or create/update it via the WP REST API[4]."""
        slug = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-")
        params = {"slug": slug}
        if parent:
            params["parent"] = parent
        resp = requests.get(
            urljoin(self.wp_url, "/wp-json/wp/v2/pages"), auth=self.auth, params=params
        )
        if resp.ok and resp.json():
            page_id = resp.json()[0]["id"]
            # Update existing page
            resp2 = requests.post(
                urljoin(self.wp_url, f"/wp-json/wp/v2/pages/{page_id}"),
                auth=self.auth,
                json={"title": title, "content": content, "status": "publish"},
            )
            resp2.raise_for_status()
            return page_id
        # Create new page
        resp3 = requests.post(
            urljoin(self.wp_url, "/wp-json/wp/v2/pages"),
            auth=self.auth,
            json={
                "title": title,
                "content": content,
                "status": "publish",
                "slug": slug,
                **({"parent": parent} if parent else {}),
            },
        )
        resp3.raise_for_status()
        return resp3.json()["id"]

    def process_folder(self, folder: Path):
        """Convert README.md (if any) to a parent page, then notebooks as children."""
        title = folder.name.replace("-", " ").title()
        md_file = folder / "README.md"
        if md_file.exists():
            html = self.convert_markdown(md_file)
        else:
            html = f"<h1>{title}</h1><p>No README.md found; default page.</p>"
        parent_id = self.get_or_create_page(title, html)
        # Process notebooks
        for nb in folder.glob("*.ipynb"):
            child_html = self.convert_notebook(nb)
            child_title = nb.stem.replace("-", " ").title()
            self.get_or_create_page(child_title, child_html, parent=parent_id)

    def run(self, root_dir: str):
        root = Path(root_dir)
        if not root.is_dir():
            raise RuntimeError(f"{root_dir} is not a directory")
        for folder in root.rglob("*"):
            if folder.is_dir():
                self.process_folder(folder)


def main():
    publisher = WordPressPublisher()
    notebooks_dir = sys.argv[1] if len(sys.argv) > 1 else "notebooks"
    publisher.run(notebooks_dir)
    print("🎉 Publishing complete!")


if __name__ == "__main__":
    main()
