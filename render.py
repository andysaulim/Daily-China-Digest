"""
China Daily Brief — HTML Renderer
CSIS China Programs

Mirrors Daily-Korea-Digest visual language exactly:
- Navy #1B2A4A header + saturated CSIS palette
- Arial/Georgia stack (NOT v3.1 Libre Baskerville)
- Status pills (rounded), status badges (small rounded)
- Colored left-borders for category coding
- Sections organised by relationship: Top Stories, US-China, China & the World,
  Economy & Business; one data band; the BEIJING chapter (Propaganda Delta,
  What Beijing Is Saying, What Beijing Did, Voices, What Others Are Saying);
  the WIRE (Overnight Flash, Also Today); What We Are Watching to close
"""

import re as _re
from datetime import datetime, timezone
from urllib.parse import urlparse as _urlparse

import wordcount