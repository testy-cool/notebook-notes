import os
import requests
import base64
import json
from pathlib import Path

class WordPressPublisher:
    def __init__(self, url, username, password):
        self.url = url.rstrip('/')
        self.auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {
            'Authorization': f'Basic {self.auth}',
            'Content-Type': 'application/json'
        }
    
    def create_category(self, name):
        """Create a category if it doesn't exist"""
        # Check if category exists
        response = requests.get(
            f"{self.url}/wp-json/wp/v2/categories",
            headers=self.headers,
            params={'search': name}
        )
        
        if response.json():
            return response.json()[0]['id']
        
        # Create new category
        data = {'name': name}
        response = requests.post(
            f"{self.url}/wp-json/wp/v2/categories",
            headers=self.headers,
            json=data
        )
        return response.json()['id']
    
    def publish_post(self, title, content, category_name):
        """Publish a post to WordPress"""
        category_id = self.create_category(category_name)
        
        post_data = {
            'title': title,
            'content': content,
            'categories': [category_id],
            'status': 'publish'
        }
        
        response = requests.post(
            f"{self.url}/wp-json/wp/v2/posts",
            headers=self.headers,
            json=post_data
        )
        
        return response.json()

def main():
    wp_url = os.environ['WP_URL']
    wp_username = os.environ['WP_USERNAME'] 
    wp_password = os.environ['WP_PASSWORD']
    
    publisher = WordPressPublisher(wp_url, wp_username, wp_password)
    
    # Process converted notebooks
    notebooks_dir = Path("notebooks")
    for md_file in notebooks_dir.rglob("*.md"):
        with open(md_file, 'r') as f:
            content = f.read()
        
        # Extract category from folder structure
        relative_path = md_file.relative_to(notebooks_dir)
        category = relative_path.parent.name
        title = md_file.stem.replace('-', ' ').replace('_', ' ').title()
        
        # Publish to WordPress
        result = publisher.publish_post(title, content, category)
        print(f"Published: {title} to category: {category}")

if __name__ == "__main__":
    main()