#!/usr/bin/env python3
import logging
import sys

# Suppress waitress queue depth warnings (normal under concurrent requests)
logging.getLogger("waitress.queue").setLevel(logging.CRITICAL)

if __name__ == "__main__":
    import waitress
    import os
    waitress.serve(
        "app.main:server",
        listen=f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '3000')}",
    )
