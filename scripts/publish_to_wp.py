#!/usr/bin/env python3
"""
publish_to_wp.py: Convert Jupyter notebooks to Markdown and publish
them as WordPress posts under folder-named categories.
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import nbformat
import requests
from nbconvert import MarkdownExporter
from requests.auth import HTTPBasicAuth


class WordPressPublisher:
    def __init__(self):
        self.wp_url = os.getenv("WP_URL")  # e.g. https://example.com [1]
        user = os.getenv("WP_USERNAME")
        pwd = os.getenv("WP_PASSWORD")
        if not (self.wp_url and user and pwd):
            raise RuntimeError("Set WP_URL, WP_USERNAME, and WP_PASSWORD")  # [2]
        if not self.wp_url.startswith(("http://", "https://")):
            raise RuntimeError("WP_URL must start with http:// or https://")  # [2]
        self.auth = HTTPBasicAuth(user, pwd)

    def convert_notebook_to_markdown(self, nb_path: Path) -> str:
        """
        Convert a .ipynb file to Markdown in-memory via nbconvert’s MarkdownExporter[3].
        """
        nb_node = nbformat.read(str(nb_path), as_version=4)
        exporter = MarkdownExporter()
        md_body, _ = exporter.from_notebook_node(nb_node)
        return md_body

    def wrap_markdown_block(self, md: str) -> str:
        """
        Wrap Markdown in a Gutenberg Markdown block so it stays editable in the editor[4].
        """
        return f"<!-- wp:markdown -->\n{md}\n<!-- /wp:markdown -->"

    def get_or_create_category(self, name: str) -> int:
        """
        Retrieve or create a WordPress category via REST API; returns its ID[5].
        """
        slug = re.sub(r"[^\w\s-]", "", name.lower()).replace(" ", "-")
        resp = requests.get(
            urljoin(self.wp_url, "/wp-json/wp/v2/categories"),
            auth=self.auth,
            params={"slug": slug},
        )
        if resp.ok and resp.json():
            return resp.json()[0]["id"]
        resp2 = requests.post(
            urljoin(self.wp_url, "/wp-json/wp/v2/categories"),
            auth=self.auth,
            json={"name": name, "slug": slug},
        )
        resp2.raise_for_status()
        return resp2.json()["id"]

    def publish_post(self, title: str, md: str, category_id: int) -> int:
        """
        Publish or update a post under the given category using the Posts API[6].
        """
        slug = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-")
        # Search for existing post by slug
        resp = requests.get(
            urljoin(self.wp_url, "/wp-json/wp/v2/posts"),
            auth=self.auth,
            params={"slug": slug},
        )
        content = self.wrap_markdown_block(md)
        data = {
            "title": title,
            "content": content,
            "status": "publish",
            "slug": slug,
            "categories": [category_id],
        }
        if resp.ok and resp.json():
            post_id = resp.json()[0]["id"]
            resp2 = requests.post(
                urljoin(self.wp_url, f"/wp-json/wp/v2/posts/{post_id}"),
                auth=self.auth,
                json=data,
            )
            resp2.raise_for_status()
            return post_id
        resp3 = requests.post(
            urljoin(self.wp_url, "/wp-json/wp/v2/posts"), auth=self.auth, json=data
        )
        resp3.raise_for_status()
        return resp3.json()["id"]

    def run(self, root_dir: str):
        """
        Traverse each subfolder under `root_dir`, create a category for the folder,
        convert each notebook to Markdown, and publish it as a post[7].
        """
        root = Path(root_dir)
        if not root.is_dir():
            raise RuntimeError(f"{root_dir} is not a valid directory")
        for folder in root.rglob("*"):
            if not folder.is_dir():
                continue
            category_name = folder.name.replace("-", " ").title()
            cat_id = self.get_or_create_category(category_name)
            for nb in folder.glob("*.ipynb"):
                title = nb.stem.replace("-", " ").title()
                md = self.convert_notebook_to_markdown(nb)
                post_id = self.publish_post(title, md, cat_id)
                print(f"Published post {post_id}: {category_name}/{title}")


def main():
    dir_arg = sys.argv[1] if len(sys.argv) > 1 else "notebooks"
    WordPressPublisher().run(dir_arg)
    print("All notebooks have been published as posts!")


if __name__ == "__main__":
    main()
