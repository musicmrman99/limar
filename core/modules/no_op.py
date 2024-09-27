from typing import Any

class NoOpModule:
    # Lifecycle
    # --------------------

    # NOTE: As a core module, this module follows the core module lifecycle,
    #       which 'wraps around' the main module lifecycle.

    def __call__(self, forwarded_data: Any, *_, **__):
        return forwarded_data
