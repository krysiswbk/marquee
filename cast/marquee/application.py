"""Composition root for the Marquee fork."""
from .runtime import Runtime


def create_application(services):
    return Runtime(services)


def main():
    from . import composition
    create_application(composition).run()
