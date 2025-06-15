#!/usr/bin/env python3
"""
WordPress Publisher for Jupyter Notebooks
Converts .ipynb files to WordPress pages with proper hierarchy and formatting
"""

import base64
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

import markdown
import requests
from bs4 import BeautifulSoup


class WordPressPublisher:
    def __init__(self):
        self.wp_url = os.getenv("WP_URL")
        self.wp_username = os.getenv("WP_USERNAME")
        self.wp_password = os.getenv("WP_PASSWORD")

        # Validate environment variables
        if not all([self.wp_url, self.wp_username, self.wp_password]):
            raise ValueError(
                "WP_URL, WP_USERNAME, and WP_PASSWORD environment variables are required"
            )

        if not self.wp_url.startswith(("http://", "https://")):
            raise ValueError("WP_URL must include http:// or https://")

        # Setup authentication
        credentials = f"{self.wp_username}:{self.wp_password}"
        self.auth_token = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {self.auth_token}",
            "Content-Type": "application/json",
        }

        print(f"✓ WordPress Publisher initialized for {self.wp_url}")

    def convert_notebook_to_markdown(self, notebook_path):
        """Convert Jupyter notebook to markdown using nbconvert"""
        try:
            # Use nbconvert to convert notebook to markdown
            result = subprocess.run(
                [
                    "jupyter",
                    "nbconvert",
                    "--to",
                    "markdown",
                    "--output-dir",
                    "/tmp",
                    str(notebook_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Get the output markdown file path
            notebook_name = Path(notebook_path).stem
            md_path = f"/tmp/{notebook_name}.md"

            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    markdown_content = f.read()
                os.remove(md_path)  # Clean up temporary file
                return markdown_content
            else:
                raise FileNotFoundError(f"Converted markdown file not found: {md_path}")

        except subprocess.CalledProcessError as e:
            raise Exception(f"nbconvert failed: {e.stderr}")
        except Exception as e:
            raise Exception(f"Notebook conversion error: {str(e)}")

    def markdown_to_html(self, markdown_content):
        """Convert markdown to WordPress-compatible HTML"""
        # Configure markdown extensions for better rendering
        extensions = [
            "codehilite",
            "tables",
            "fenced_code",
            "toc",
            "nl2br",
            "sane_lists",
        ]

        # Convert markdown to HTML
        html_content = markdown.markdown(
            markdown_content,
            extensions=extensions,
            extension_configs={
                "codehilite": {"css_class": "highlight", "use_pygments": True}
            },
        )

        # Clean up HTML for WordPress compatibility
        soup = BeautifulSoup(html_content, "html.parser")

        # Add proper CSS classes for WordPress themes
        for code_block in soup.find_all("div", class_="highlight"):
            code_block["class"] = ["wp-block-code", "highlight"]

        for table in soup.find_all("table"):
            table["class"] = ["wp-block-table"]

        return str(soup)

    def get_or_create_page(self, title, content, parent_id=None):
        """Get existing page or create new one"""
        # First, try to find existing page by title
        search_url = urljoin(self.wp_url, "/wp-json/wp/v2/pages")
        params = {"search": title}

        if parent_id:
            params["parent"] = parent_id

        response = requests.get(search_url, headers=self.headers, params=params)

        if response.status_code == 200:
            pages = response.json()
            for page in pages:
                if page["title"]["rendered"].strip() == title.strip():
                    print(f"✓ Found existing page: {title}")
                    return page["id"]

        # Create new page if not found
        return self.create_page(title, content, parent_id)

    def create_page(self, title, content, parent_id=None):
        """Create a new WordPress page"""
        url = urljoin(self.wp_url, "/wp-json/wp/v2/pages")

        page_data = {
            "title": title,
            "content": content,
            "status": "publish",
            "slug": self.generate_slug(title),
        }

        if parent_id:
            page_data["parent"] = parent_id

        response = requests.post(url, headers=self.headers, json=page_data)

        if response.status_code == 201:
            page_id = response.json()["id"]
            print(f"✓ Created page: {title} (ID: {page_id})")
            return page_id
        else:
            error_msg = f"Failed to create page '{title}': {response.status_code} - {response.text}"
            print(f"✗ {error_msg}")
            raise Exception(error_msg)

    def update_page(self, page_id, title, content):
        """Update an existing WordPress page"""
        url = urljoin(self.wp_url, f"/wp-json/wp/v2/pages/{page_id}")

        page_data = {"title": title, "content": content, "status": "publish"}

        response = requests.post(url, headers=self.headers, json=page_data)

        if response.status_code == 200:
            print(f"✓ Updated page: {title} (ID: {page_id})")
            return page_id
        else:
            error_msg = f"Failed to update page '{title}': {response.status_code} - {response.text}"
            print(f"✗ {error_msg}")
            raise Exception(error_msg)

    def generate_slug(self, title):
        """Generate URL-friendly slug from title"""
        import re

        slug = title.lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug.strip("-")

    def process_folder_structure(self, notebooks_dir="notebooks"):
        """Process entire folder structure and publish to WordPress"""
        notebooks_path = Path(notebooks_dir)

        if not notebooks_path.exists():
            raise FileNotFoundError(f"Notebooks directory not found: {notebooks_dir}")

        print(f"📁 Processing notebooks from: {notebooks_path}")

        # Process each folder
        for folder_path in notebooks_path.iterdir():
            if folder_path.is_dir():
                self.process_folder(folder_path)

    def process_folder(self, folder_path):
        """Process a single folder and its contents"""
        folder_name = folder_path.name
        print(f"\n📂 Processing folder: {folder_name}")

        # Check for README.md in folder
        readme_path = folder_path / "README.md"
        folder_content = ""

        if readme_path.exists():
            with open(readme_path, "r", encoding="utf-8") as f:
                folder_markdown = f.read()
            folder_content = self.markdown_to_html(folder_markdown)
            print(f"✓ Found README.md for folder: {folder_name}")
        else:
            # Create default folder content
            folder_content = f"<h1>{folder_name.replace('-', ' ').title()}</h1>\n<p>Collection of notebooks in the {folder_name} category.</p>"
            print(f"ℹ No README.md found, using default content for: {folder_name}")

        # Create or get folder page
        folder_title = folder_name.replace("-", " ").replace("_", " ").title()
        folder_page_id = self.get_or_create_page(folder_title, folder_content)

        # Process notebooks in folder
        for notebook_path in folder_path.glob("*.ipynb"):
            self.process_notebook(notebook_path, folder_page_id)

    def process_notebook(self, notebook_path, parent_page_id):
        """Process a single notebook and publish as child page"""
        notebook_name = notebook_path.stem
        print(f"📓 Processing notebook: {notebook_name}")

        try:
            # Convert notebook to markdown
            markdown_content = self.convert_notebook_to_markdown(notebook_path)

            # Convert markdown to HTML
            html_content = self.markdown_to_html(markdown_content)

            # Create page title from notebook name
            page_title = notebook_name.replace("-", " ").replace("_", " ").title()

            # Create or update page
            page_id = self.get_or_create_page(page_title, html_content, parent_page_id)

            print(f"✓ Published notebook: {page_title}")

        except Exception as e:
            print(f"✗ Failed to process {notebook_name}: {str(e)}")


def main():
    """Main function to run the WordPress publisher"""
    try:
        # Initialize publisher
        publisher = WordPressPublisher()

        # Get notebooks directory from command line or use default
        notebooks_dir = sys.argv[1] if len(sys.argv) > 1 else "notebooks"

        # Process all folders and notebooks
        publisher.process_folder_structure(notebooks_dir)

        print("\n🎉 Publishing completed successfully!")

    except Exception as e:
        print(f"\n💥 Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
