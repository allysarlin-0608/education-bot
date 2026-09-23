import logging

# Details of failed AI / database calls go here (Streamlit Cloud: Manage
# app → logs), never onto the page.
_logger = logging.getLogger("coach")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
