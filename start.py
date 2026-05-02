#!/usr/bin/env python3
import logging
import os
import sys

# Suppress waitress queue depth warnings
logging.getLogger("waitress.queue").setLevel(logging.CRITICAL)

if __name__ == "__main__":
    import waitress
    from app.main import server

    waitress.serve(
        server,
        listen=f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '3000')}",
    )
