# This file makes the extraction folder a Python module.
# You can add imports here if you want to expose certain functions directly from the module.

from .contact_extractor import contact_info
from .section_splitter import splitter

__all__ = ["contact_info", "splitter"]
