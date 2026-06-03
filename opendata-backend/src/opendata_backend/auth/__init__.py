"""Clerk authentication primitives.

`ClerkUser` is the parsed identity returned by `require_user`. Each router
that needs authentication declares `user: ClerkUser = Depends(require_user)`
on its handlers.
"""

from .clerk import ClerkAuthError, ClerkUser, verify_clerk_token
from .dependencies import require_user

__all__ = ["ClerkAuthError", "ClerkUser", "require_user", "verify_clerk_token"]
