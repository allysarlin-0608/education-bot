"""Errors other modules catch by class. Kept loaded when new code is loaded
(coach.freshen: SERVER_SIDE): a session whose run began on the old code
raises the old class while its page, re-importing, catches with the new
one; the same class in both is what makes `except StorageError` hold."""


class StorageError(Exception):
    """str(e) is safe to show the user; details are logged, not shown.
    status is the HTTP status (None for connection problems)."""

    def __init__(self, message, status=None, detail=""):
        super().__init__(message)
        self.status = status
        self.detail = detail     # the raw response, for code paths only
