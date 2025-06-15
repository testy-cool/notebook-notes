import os
import subprocess
import json
from pathlib import Path

def convert_notebooks():
    notebooks_dir = Path("notebooks")
    converted = []
    
    for notebook_path in notebooks_dir.rglob("*.ipynb"):
        # Convert to markdown
        cmd = f"jupyter nbconvert --to markdown '{notebook_path}'"
        subprocess.run(cmd, shell=True)
        
        # Get folder structure for categorization
        relative_path = notebook_path.relative_to(notebooks_dir)
        category = relative_path.parent.name if relative_path.parent != Path('.') else 'uncategorized'
        
        converted.append({
            'notebook': str(notebook_path),
            'markdown': str(notebook_path.with_suffix('.md')),
            'category': category,
            'title': notebook_path.stem.replace('-', ' ').replace('_', ' ').title()
        })
    
    return converted
