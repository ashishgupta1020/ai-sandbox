#!/usr/bin/env python3
"""
Markdown utilities for rendering formatted text
"""

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    print("Warning: markdown library not available. Install with: pip install markdown")


def render_markdown(text: str) -> str:
    """Render markdown text to plain text with basic formatting"""
    if not MARKDOWN_AVAILABLE or not text.strip():
        return text
    
    try:
        # Convert markdown to HTML
        html = markdown.markdown(text, extensions=['fenced_code', 'tables', 'codehilite'])
        
        # Simple HTML to plain text conversion for display
        # Remove HTML tags but preserve some formatting
        import re
        
        # Replace common HTML elements with plain text equivalents
        html = re.sub(r'<h[1-6]>(.*?)</h[1-6]>', r'\n\1\n', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<p>(.*?)</p>', r'\1\n', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<br\s*/?>', r'\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<strong>(.*?)</strong>', r'**\1**', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<em>(.*?)</em>', r'*\1*', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<code>(.*?)</code>', r'`\1`', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<pre><code>(.*?)</code></pre>', r'\n```\n\1\n```\n', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<ul>(.*?)</ul>', r'\1', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<ol>(.*?)</ol>', r'\1', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<li>(.*?)</li>', r'• \1\n', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<blockquote>(.*?)</blockquote>', r'\n> \1\n', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove any remaining HTML tags
        html = re.sub(r'<[^>]+>', '', html)
        
        # Decode HTML entities
        import html as html_module
        text_result = html_module.unescape(html)
        
        # Clean up extra whitespace
        text_result = re.sub(r'\n\s*\n\s*\n', '\n\n', text_result)
        text_result = text_result.strip()
        
        return text_result
    except Exception as e:
        # If markdown rendering fails, return original text
        print(f"Warning: Markdown rendering failed: {e}")
        return text
