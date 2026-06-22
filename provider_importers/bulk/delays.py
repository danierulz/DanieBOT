"""Shared rate-limit delays for bulk provider scraping."""

# Pause between individual product fetches during bulk import (API/CLI).
REQUEST_DELAY_SECONDS = 1.5

# Pause between catalog listing page requests during URL discovery.
LISTING_PAGE_DELAY_SECONDS = 1.0

# CLI default (--delay-ms); kept in sync with REQUEST_DELAY_SECONDS.
REQUEST_DELAY_MS = int(REQUEST_DELAY_SECONDS * 1000)
