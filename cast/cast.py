#!/usr/bin/env python3
"""Small executable entrypoint for the Marquee fork."""
import sys

from marquee.application import main


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        from marquee.config import validate_config
        from marquee.providers.registry import DEFAULT_CONFIG
        validate_config(DEFAULT_CONFIG)
        print("selftest ok")
    else:
        main()
