# Sources

1. Create a new module in `pyobo.sources` named with the prefix for the resource you're ontologizing
2. Make sure your resource has a corresponding prefix in [the Bioregistry](https://github.com/biopragmatics/bioregistry)
3. Subclass the `pyobo.Obo` class to represent your resource
4. Add your resource to the list in `pyobo.sources.__init__`

## What is in scope?

1. Biomedical, semantic web, bibliographic, life sciences, and related natural sciences resources are welcome
2. The source you want to ontologize should be an identifier resource, i.e., it mints its own identifiers. If you want
   to ontologize some database that reuses some other identifier resource's identifiers, then this isn't the right
   place.
3. Resources that are not possible to download automatically are not in scope for PyOBO. Reproducibility and reusability
   are core values of this software
