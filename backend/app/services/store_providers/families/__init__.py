"""Reusable provider implementations.

A "family" is a provider parameterised by configuration rather than written
per store. Adding a chain that fits one is a line in ``definitions.py``:

- ``html_catalog`` — any store whose search page is server-rendered with
  schema.org Product microdata (Auchan today).
- ``magento``      — any Magento 2 storefront (Biocoop, Naturalia).
- ``extension``    — any store behind an anti-bot shield, reached through the
  user's own browser (Carrefour, and Intermarché / Leclerc when wanted).
- ``openprices``   — the Open Food Facts price database; one API, not a family,
  but the same contract.
"""
