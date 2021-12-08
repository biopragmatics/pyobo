# -*- coding: utf-8 -*-

"""Utilities for OBO files."""

import datetime
import gzip
import json
import logging
import pathlib
import typing
import urllib.error
import warnings
from collections import Counter
from typing import (
    Callable,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
)

import bioregistry
from pystow.utils import download
from tqdm import tqdm

from .constants import DATABASE_DIRECTORY
from .identifier_utils import MissingPrefix, wrap_norm_prefix
from .plugins import has_nomenclature_plugin, run_nomenclature_plugin
from .reader import from_obo_path, from_obonet
from .struct import Obo
from .utils.cache import get_gzipped_graph
from .utils.io import get_writer
from .utils.path import ensure_path, get_prefix_obo_path, prefix_directory_join
from .version import get_git_hash, get_version

__all__ = [
    "get_ontology",
    "NoBuild",
]

logger = logging.getLogger(__name__)


class NoBuild(RuntimeError):
    """Base exception for being unable to build."""


class UnhandledFormat(NoBuild):
    """Only OWL is available."""


@wrap_norm_prefix
def get_ontology(
    prefix: str,
    *,
    force: bool = False,
    rewrite: bool = False,
    url: Optional[str] = None,
    strict: bool = True,
    version: Optional[str] = None,
) -> Obo:
    """Get the OBO for a given graph.

    :param prefix: The prefix of the ontology to look up
    :param version: The pre-looked-up version of the ontology
    :param force: Download the data again
    :param rewrite: Should the OBO cache be rewritten? Automatically set to true if ``force`` is true
    :param url: A URL to give if the OBOfoundry can not be used to look up the given prefix. This option is deprecated,
        you should make a PR to the bioregistry or use other code if you have a custom URL, like:
    :param strict: Should CURIEs be treated strictly? If true, raises exceptions on invalid/malformed
    :returns: An OBO object

    :raises OnlyOWLError: If the OBO foundry only has an OWL document for this resource.

    Alternate usage if you have a custom url::

    >>> from pystow.utils import download
    >>> from pyobo import Obo, from_obo_path
    >>> url = ...
    >>> obo_path = ...
    >>> download(url=url, path=path)
    >>> obo = from_obo_path(path)
    """
    if force:
        rewrite = True
    if prefix == "uberon":
        logger.info("UBERON has so much garbage in it that defaulting to non-strict parsing")
        strict = False

    obonet_json_gz_path = prefix_directory_join(
        prefix, name=f"{prefix}.obonet.json.gz", ensure_exists=False, version=version
    )
    if obonet_json_gz_path.exists() and not force:
        logger.debug("[%s] using obonet cache at %s", prefix, obonet_json_gz_path)
        return from_obonet(get_gzipped_graph(obonet_json_gz_path))

    if has_nomenclature_plugin(prefix):
        obo = run_nomenclature_plugin(prefix)
        logger.info("[%s] caching nomenclature plugin", prefix)
        obo.write_default(force=rewrite)
        return obo

    logger.debug("[%s] no obonet cache found at %s", prefix, obonet_json_gz_path)
    path = _ensure_ontology_path(prefix, url=url, force=force, version=version)

    if path.suffix == ".obo":
        pass  # all gucci
    elif path.suffix == ".owl":
        import pronto

        try:
            prontology = pronto.Ontology(path)
        except KeyError:
            raise NoBuild(f"[{prefix}] could not parse OWL with pronto") from None
        version = prontology.metadata.data_version
        # prefix = prontology.metadata.ontology
        path = get_prefix_obo_path(prefix=prefix, version=version)
        with path.open("wb") as file:
            prontology.dump(file, format="obo")
    else:
        raise UnhandledFormat(f"[{prefix}] unhandled ontology file format: {path.suffix}")
    obo = from_obo_path(path, prefix=prefix, strict=strict)
    if version is not None:
        if obo.data_version is None:
            logger.warning("[%s] did not have a version, overriding with %s", obo.ontology, version)
            obo.data_version = version
        elif obo.data_version != version:
            logger.warning(
                "[%s] had version %s, overriding with %s", obo.ontology, obo.data_version, version
            )
            obo.data_version = version
    obo.write_default(force=rewrite)
    return obo


def _ensure_ontology_path(
    prefix: str, *, url: Optional[str] = None, force: bool = False, version: Optional[str] = None
) -> pathlib.Path:
    """Get the path to the ontology file and download if missing."""
    if url is not None:
        warnings.warn("Should make curations in the bioregistry instead", DeprecationWarning)
        path = get_prefix_obo_path(prefix, version=version)
        download(url=url, path=path, force=force)
        return path

    path = get_prefix_obo_path(prefix, version=version)
    if path.is_file():
        logger.debug("[%s] OBO already exists at %s", prefix, path)
        return path

    for url in [
        bioregistry.get_obo_download(prefix),
        bioregistry.get_owl_download(prefix),
        bioregistry.get_json_download(prefix),
    ]:
        if url is not None:
            return pathlib.Path(ensure_path(prefix, url=url, force=force, version=version))

    raise NoBuild(f"could not find a download link for {prefix}")


#: Obonet/Pronto can't parse these (consider converting to OBO with ROBOT?)
CANT_PARSE = {
    "agro",
    "aro",
    "bco",
    "caro",
    "cco",
    "chmo",
    "cido",
    "covoc",
    "cto",
    "cvdo",
    "dicom",
    "dinto",
    "emap",
    "epso",
    "eupath",
    "fbbi",
    "fma",
    "fobi",
    "foodon",
    "genepio",
    "hancestro",
    "hom",
    "hso",
    "htn",  # Unknown string format: creation: 16MAY2017
    "ico",
    "idocovid19",
    "labo",
    "mamo",
    "mfmo",
    "mfo",
    "mfomd",
    "miapa",
    "mo",
    "oae",
    "ogms",  # Unknown string format: creation: 16MAY2017
    "ohd",
    "ons",
    "oostt",
    "opmi",
    "ornaseq",
    "orth",
    "pdro",
    "probonto",
    "psdo",
    "rex",
    "rnao",
    "sepio",
    "sio",
    "spd",
    "sweetrealm",
    "txpo",
    "vido",
    "vt",
    "xl",
}
SKIP = {
    "ncbigene",  # too big, refs acquired from other dbs
    "pubchem.compound",  # to big, can't deal with this now
    "gaz",  # Gazetteer is irrelevant for biology
    "ma",  # yanked
    "bila",  # yanked
    # Only OWL
    "gorel",
    # FIXME below
    "emapa",  # recently changed with EMAP... not sure what the difference is anymore
    "kegg.genes",
    "kegg.genome",
    "kegg.pathway",
    # URL is wrong
    "ensemblglossary",
    *CANT_PARSE,
}

X = TypeVar("X")


def iter_helper(
    f: Callable[[str], Mapping[str, X]],
    leave: bool = False,
    strict: bool = True,
    **kwargs,
) -> Iterable[Tuple[str, str, X]]:
    """Yield all mappings extracted from each database given."""
    for prefix, mapping in iter_helper_helper(f, strict=strict, **kwargs):
        it = tqdm(
            mapping.items(),
            desc=f"iterating {prefix}",
            leave=leave,
            unit_scale=True,
            disable=None,
        )
        for key, value in it:
            yield prefix, key, value


def iter_helper_helper(
    f: Callable[[str], X],
    use_tqdm: bool = True,
    skip_below: Optional[str] = None,
    skip_pyobo: bool = False,
    skip_set: Optional[Set[str]] = None,
    strict: bool = True,
    **kwargs,
) -> Iterable[Tuple[str, X]]:
    """Yield all mappings extracted from each database given.

    :param f: A function that takes a prefix and gives back something that will be used by an outer function.
    :param use_tqdm: If true, use the tqdm progress bar
    :param skip_below: If true, skip sources whose names are less than this (used for iterative curation
    :param skip_pyobo: If true, skip sources implemented in PyOBO
    :param skip_set: A pre-defined blacklist to skip
    :param strict: If true, will raise exceptions and crash the program instead of logging them.
    :param kwargs: Keyword arguments passed to ``f``.
    :yields: A prefix and the result of the callable ``f``

    :raises TypeError: If a type error is raised, it gets re-raised
    :raises urllib.error.HTTPError: If the resource could not be downloaded
    :raises urllib.error.URLError: If another problem was encountered during download
    :raises ValueError: If the data was not in the format that was expected (e.g., OWL)
    """
    it = tqdm(sorted(bioregistry.read_registry()), disable=not use_tqdm, desc="Resources")
    for prefix in it:
        if use_tqdm:
            it.set_postfix({"prefix": prefix})
        if bioregistry.has_no_terms(prefix):
            continue
        if prefix in SKIP:
            tqdm.write(f"skipping {prefix} because in default skip set")
            continue
        if skip_set and prefix in skip_set:
            tqdm.write(f"skipping {prefix} because in skip set")
            continue
        if skip_below is not None and prefix < skip_below:
            continue
        if skip_pyobo and has_nomenclature_plugin(prefix):
            continue
        try:
            yv = f(prefix, **kwargs)  # type:ignore
        except NoBuild:
            continue
        except urllib.error.HTTPError as e:
            logger.warning("[%s] HTTP %s: unable to download %s", prefix, e.getcode(), e.geturl())
            if strict and not bioregistry.is_deprecated(prefix):
                raise
        except urllib.error.URLError:
            logger.warning("[%s] unable to download", prefix)
            if strict and not bioregistry.is_deprecated(prefix):
                raise
        except MissingPrefix as e:
            logger.warning("[%s] missing prefix: %s", prefix, e)
            if strict and not bioregistry.is_deprecated(prefix):
                raise e
        except ValueError as e:
            if _is_xml(e):
                # this means that it tried doing parsing on an xml page saying get the fuck out
                logger.info(
                    "no resource available for %s. See http://www.obofoundry.org/ontology/%s",
                    prefix,
                    prefix,
                )
            else:
                logger.exception("[%s] error while parsing: %s", prefix, e.__class__)
            if strict:
                raise e
        except TypeError as e:
            logger.exception("TypeError on %s", prefix)
            if strict:
                raise e
        else:
            yield prefix, yv


def _is_xml(e) -> bool:
    return str(e).startswith("Tag-value pair parsing failed for:") or str(e).startswith(
        'Tag-value pair parsing failed for:\n<?xml version="1.0" encoding="UTF-8"?>'
    )


def _prep_dir(directory: Union[None, str, pathlib.Path]) -> pathlib.Path:
    if directory is None:
        rv = DATABASE_DIRECTORY
    elif isinstance(directory, str):
        rv = pathlib.Path(directory)
    elif isinstance(directory, pathlib.Path):
        rv = directory
    else:
        raise TypeError
    rv.mkdir(parents=True, exist_ok=True)
    return rv


def db_output_helper(
    f: Callable[..., Iterable[Tuple[str, ...]]],
    db_name: str,
    columns: Sequence[str],
    *,
    directory: Union[None, str, pathlib.Path] = None,
    strict: bool = True,
    use_gzip: bool = True,
    summary_detailed: Optional[Sequence[int]] = None,
    **kwargs,
) -> List[pathlib.Path]:
    """Help output database builds.

    :param f: A function that takes a prefix and gives back something that will be used by an outer function.
    :param db_name: name of the output resource (e.g., "alts", "names")
    :param columns: The names of the columns
    :param directory: The directory to output everything, or defaults to :data:`pyobo.constants.DATABASE_DIRECTORY`.
    :param strict: Passed to ``f`` by keyword
    :param kwargs: Passed to ``f`` by splat
    :returns: A sequence of paths that got created.
    """
    directory = _prep_dir(directory)

    c: typing.Counter[str] = Counter()
    c_detailed: typing.Counter[Tuple[str, ...]] = Counter()

    if use_gzip:
        db_path = directory.joinpath(f"{db_name}.tsv.gz")
    else:
        db_path = directory.joinpath(f"{db_name}.tsv")
    db_sample_path = directory.joinpath(f"{db_name}_sample.tsv")
    db_summary_path = directory.joinpath(f"{db_name}_summary.tsv")
    db_summary_detailed_path = directory.joinpath(f"{db_name}_summary_detailed.tsv")

    logger.info("writing %s to %s", db_name, db_path)
    logger.info("writing %s sample to %s", db_name, db_sample_path)
    it = f(strict=strict, **kwargs)
    with gzip.open(db_path, mode="wt") if use_gzip else open(db_path, "w") as gzipped_file:
        writer = get_writer(gzipped_file)

        # for the first 10 rows, put it in a sample file too
        with open(db_sample_path, "w") as sample_file:
            sample_writer = get_writer(sample_file)

            # write header
            writer.writerow(columns)
            sample_writer.writerow(columns)

            for row, _ in zip(it, range(10)):
                c[row[0]] += 1
                if summary_detailed is not None:
                    c_detailed[tuple(row[i] for i in summary_detailed)] += 1
                writer.writerow(row)
                sample_writer.writerow(row)

        # continue just in the gzipped one
        for row in it:
            c[row[0]] += 1
            if summary_detailed is not None:
                c_detailed[tuple(row[i] for i in summary_detailed)] += 1
            writer.writerow(row)

    logger.info(f"writing {db_name} summary to {db_summary_path}")
    with open(db_summary_path, "w") as file:
        writer = get_writer(file)
        writer.writerows(c.most_common())

    if summary_detailed is not None:
        logger.info(f"writing {db_name} detailed summary to {db_summary_detailed_path}")
        with open(db_summary_detailed_path, "w") as file:
            writer = get_writer(file)
            writer.writerows((*keys, v) for keys, v in c_detailed.most_common())

    db_metadata_path = directory.joinpath(f"{db_name}_metadata.json")
    with open(db_metadata_path, "w") as file:
        json.dump(
            {
                "version": get_version(),
                "git_hash": get_git_hash(),
                "date": datetime.datetime.now().strftime("%Y-%m-%d-%H-%M"),
                "count": sum(c.values()),
            },
            file,
            indent=2,
        )

    rv: List[pathlib.Path] = [
        db_metadata_path,
        db_path,
        db_sample_path,
        db_summary_path,
    ]
    if summary_detailed:
        rv.append(db_summary_detailed_path)
    return rv
