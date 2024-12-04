"""CLI for UMLS exporter."""

from .umls import UMLSGetter

if __name__ == "__main__":
    UMLSGetter.cli()
