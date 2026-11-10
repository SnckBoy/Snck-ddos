# Compatibility import for deployments that previously used web.app.
# The unrestricted control panel has been retired on this safe branch.
from command_center import app

__all__ = ["app"]
