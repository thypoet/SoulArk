#!/usr/bin/env python3
"""
SoulArk Tool: Web Search
Uses DuckDuckGo (no API key required) to search the web.
"""

import requests
import json
from urllib.parse import quote_plus


def search(query, max_results=5):
    """
    Search the web using DuckDuckGo's HTML endpoint.
    Returns a list of results with title, url, and snippet.
    """
    results = []

    try:
        # Use DuckDuckGo's API-like endpoint
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_redirect=1&no_html=1"
        headers = {"User-Agent": "SoulArk/0.2"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        # Abstract (instant answer)
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", "Result"),
                "url": data.get("AbstractURL", ""),
                "snippet": data["Abstract"]
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if "Text" in topic:
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", "")
                })

        # If DuckDuckGo instant answers didn't return much, try the lite endpoint
        if len(results) < 2:
            lite_results = _search_lite(query, max_results)
            results.extend(lite_results)

    except Exception as e:
        results.append({
            "title": "Search error",
            "url": "",
            "snippet": f"Could not complete search: {e}"
        })

    return results[:max_results]


def _search_lite(query, max_results=5):
    """Fallback: scrape DuckDuckGo lite for results."""
    results = []
    try:
        url = "https://lite.duckduckgo.com/lite/"
        response = requests.post(
            url,
            data={"q": query},
            headers={"User-Agent": "SoulArk/0.2"},
            timeout=10
        )
        text = response.text

        # Basic extraction from lite HTML
        # Find result links and snippets
        import re
        links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*class="result-link"[^>]*>([^<]+)</a>', text)
        snippets = re.findall(r'<td class="result-snippet">([^<]+)</td>', text)

        for i, (link_url, title) in enumerate(links[:max_results]):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append({
                "title": title.strip(),
                "url": link_url.strip(),
                "snippet": snippet.strip()
            })

    except Exception:
        pass

    return results


def fetch_page(url, max_chars=3000):
    """Fetch a webpage and return its text content (stripped of HTML)."""
    try:
        headers = {"User-Agent": "SoulArk/0.2"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Basic HTML to text
        import re
        text = response.text
        # Remove scripts and styles
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text[:max_chars]

    except Exception as e:
        return f"Could not fetch page: {e}"


# Tool definition for OpenRouter/OpenAI function calling format
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the internet for current information. Use this when you need to find recent news, look up facts, check current events, or answer questions that require up-to-date information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
}

FETCH_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": "Fetch and read the contents of a specific webpage URL. Use this after web_search to read full articles or pages.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch"
                }
            },
            "required": ["url"]
        }
    }
}
TOOL_NAME = "web_search"
TOOL_DESCRIPTION = "Search the web using DuckDuckGo. Pass a query string."

def run(args, agent_dir):
    query = args.get("query", args.get("input", ""))
    if not query:
        return json.dumps({"status": "error", "error": "No query provided"})
    results = search(query)
    return json.dumps({"status": "ok", "results": results})

