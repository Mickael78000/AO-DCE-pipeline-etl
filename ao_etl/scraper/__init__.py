"""Module de scraping pour enrichir les données LLM depuis les URLs."""

from .url_scraper import scrape_url, enrich_row_with_url_content

__all__ = ["scrape_url", "enrich_row_with_url_content"]
