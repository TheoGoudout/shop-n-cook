"""Import top-rated recipes from well-known recipe sites, in the background.

- sites.py: the sites crawled, and why each one is (or is not) on the list
- discovery.py: recipe URLs from a site's popularity pages; canonical URLs
- quality.py: the rating gate and the ranking
- crawler.py: one pass — judge, rank, import, remember (``crawl`` / ``run_crawl``)
- scheduler.py: runs a pass every ``RECIPE_CRAWL_HOURS`` (0, the default, is off)

Run one pass by hand with ``python -m app.services.recipe_crawler`` (add
``--dry-run`` to see what would be imported without importing it).
"""
