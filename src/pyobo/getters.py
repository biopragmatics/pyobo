"""Utilities for OBO files."""

from __future__ import annotations

import datetime
import json
import logging
import pathlib
import subprocess
import time
import typing
import urllib.error
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from textwrap import indent
from typing import Any, TypeVar

import bioregistry
import click
import pystow.utils
from tabulate import tabulate
from tqdm.auto import tqdm
from typing_extensions import Unpack

from .constants import (
    BUILD_SUBDIRECTORY_NAME,
    DATABASE_DIRECTORY,
    GetOntologyKwargs,
    IterHelperHelperDict,
    SlimGetOntologyKwargs,
)
from .identifier_utils import ParseError, wrap_norm_prefix
from .plugins import has_nomenclature_plugin, run_nomenclature_plugin
from .struct import Obo
from .struct.obo import from_obo_path, from_obonet
from .utils.io import safe_open_writer
from .utils.path import ensure_path, prefix_directory_join
from .version import get_git_hash, get_version

__all__ = [
    "NoBuildError",
    "get_ontology",
]

logger = logging.getLogger(__name__)


class NoBuildError(RuntimeError):
    """Base exception for being unable to build."""


class UnhandledFormatError(NoBuildError):
    """Only OWL is available."""


#: The following prefixes can not be loaded through ROBOT without
#: turning off integrity checks
REQUIRES_NO_ROBOT_CHECK = {
    "clo",
    "vo",
    "orphanet.ordo",
    "orphanet",
    "foodon",
    "caloha",
}


@wrap_norm_prefix
def get_ontology(
    prefix: str,
    *,
    force: bool = False,
    force_process: bool = False,
    strict: bool = False,
    version: str | None = None,
    robot_check: bool = True,
    upgrade: bool = True,
    cache: bool = True,
    use_tqdm: bool = True,
) -> Obo:
    """Get the OBO for a given graph.

    :param prefix: The prefix of the ontology to look up
    :param version: The pre-looked-up version of the ontology
    :param force: Download the data again
    :param force_process: Should the OBO cache be rewritten? Automatically set to true
        if ``force`` is true
    :param strict: Should CURIEs be treated strictly? If true, raises exceptions on
        invalid/malformed
    :param robot_check: If set to false, will send the ``--check=false`` command to
        ROBOT to disregard malformed ontology components. Necessary to load some
        ontologies like VO.
    :param upgrade: If set to true, will automatically upgrade relationships, such as
        ``obo:chebi#part_of`` to ``BFO:0000051``
    :param cache: Should cached objects be written? defaults to True

    :returns: An OBO object

    :raises OnlyOWLError: If the OBO foundry only has an OWL document for this resource.

    Alternate usage if you have a custom url

    .. code-block:: python

        from pystow.utils import download
        from pyobo import Obo, from_obo_path

        url = ...
        obo_path = ...
        download(url=url, path=path)
        obo = from_obo_path(path)
    """
    if force:
        force_process = True
    if prefix == "uberon":
        logger.info("UBERON has so much garbage in it that defaulting to non-strict parsing")
        strict = False

    if force_process:
        obonet_json_gz_path = None
    elif not cache:
        logger.debug("[%s] caching was turned off, so dont look for an obonet file", prefix)
        obonet_json_gz_path = None
    else:
        obonet_json_gz_path = prefix_directory_join(
            prefix, BUILD_SUBDIRECTORY_NAME, name=f"{prefix}.obonet.json.gz", version=version
        )
        logger.debug(
            "[%s] caching is turned on, so look for an obonet file at %s",
            prefix,
            obonet_json_gz_path,
        )
        if obonet_json_gz_path.is_file() and not force:
            from .utils.cache import get_gzipped_graph

            logger.debug("[%s] using obonet cache at %s", prefix, obonet_json_gz_path)
            return from_obonet(
                get_gzipped_graph(obonet_json_gz_path),
                strict=strict,
                version=version,
                upgrade=upgrade,
                use_tqdm=use_tqdm,
            )
        else:
            logger.debug("[%s] no obonet cache found at %s", prefix, obonet_json_gz_path)

    if has_nomenclature_plugin(prefix):
        obo = run_nomenclature_plugin(prefix, version=version)
        if cache:
            logger.debug("[%s] caching nomenclature plugin", prefix)
            obo.write_default(force=force_process)
        return obo

    ontology_format, path = _ensure_ontology_path(prefix, force=force, version=version)
    if path is None:
        raise NoBuildError(prefix)
    elif ontology_format == "obo":
        pass  # all gucci
    elif ontology_format == "owl":
        import bioontologies.robot

        _converted_obo_path = path.with_suffix(".obo")
        if prefix in REQUIRES_NO_ROBOT_CHECK:
            robot_check = False
        bioontologies.robot.convert(path, _converted_obo_path, check=robot_check)
        path = _converted_obo_path
    elif ontology_format == "json":
        from .struct.obograph import read_obograph

        obo = read_obograph(prefix=prefix, path=path)
        if cache:
            obo.write_default(force=force_process)
        return obo
    else:
        raise UnhandledFormatError(f"[{prefix}] unhandled ontology file format: {path.suffix}")

    obo = from_obo_path(
        path,
        prefix=prefix,
        strict=strict,
        version=version,
        upgrade=upgrade,
        use_tqdm=use_tqdm,
        _cache_path=obonet_json_gz_path,
    )
    if cache:
        obo.write_default(force=force_process)
    return obo


def _ensure_ontology_path(
    prefix: str, force: bool, version: str | None
) -> tuple[str, Path] | tuple[None, None]:
    for ontology_format, url in [
        ("obo", bioregistry.get_obo_download(prefix)),
        ("owl", bioregistry.get_owl_download(prefix)),
        ("json", bioregistry.get_json_download(prefix)),
    ]:
        if url is not None:
            try:
                path = ensure_path(prefix, url=url, force=force, version=version)
            except (urllib.error.HTTPError, pystow.utils.DownloadError):
                continue
            else:
                return ontology_format, path
    return None, None


SKIP = {
    "ncbigene": "too big, refs acquired from other dbs",
    "pubchem.compound": "top big, can't deal with this now",
    "gaz": "Gazetteer is irrelevant for biology",
    "ma": "yanked",
    "bila": "yanked",
    # Can't download",
    "afpo": "unable to download",
    "atol": "unable to download",
    "eol": "unable to download, same source as atol",
    "hog": "unable to download",
    "vhog": "unable to download",
    "gorel": "unable to download",
    "dinto": "unable to download",
    "gainesville.core": "unable to download",
    "ato": "can't process",
    "emapa": "recently changed with EMAP... not sure what the difference is anymore",
    "kegg.genes": "needs fix",  # FIXME
    "kegg.genome": "needs fix",  # FIXME
    "kegg.pathway": "needs fix",  # FIXME
    "ensemblglossary": "URI is self-referential to data in OLS, extract from there",
    "epio": "content from fraunhofer is unreliable",
    "epso": "content from fraunhofer is unreliable",
    "gwascentral.phenotype": "website is down? or API changed?",  # FIXME
    "gwascentral.study": "website is down? or API changed?",  # FIXME
    "snomedct": "dead source",
}

X = TypeVar("X")


def iter_helper(
    f: Callable[[str, Unpack[GetOntologyKwargs]], Mapping[str, X]],
    leave: bool = False,
    **kwargs: Unpack[IterHelperHelperDict],
) -> Iterable[tuple[str, str, X]]:
    """Yield all mappings extracted from each database given."""
    for prefix, mapping in iter_helper_helper(f, **kwargs):
        it = tqdm(
            mapping.items(),
            desc=f"iterating {prefix}",
            leave=leave,
            unit_scale=True,
            disable=None,
        )
        for key, value in it:
            if isinstance(value, str):
                value = value.strip('"').replace("\n", " ").replace("\t", " ").replace("  ", " ")
            # TODO deal with when this is not a string?
            if value:
                yield prefix, key, value


def _prefixes(
    skip_below: str | None = None,
    skip_below_inclusive: bool = True,
    skip_pyobo: bool = False,
    skip_set: set[str] | None = None,
) -> Iterable[str]:
    for prefix, resource in sorted(bioregistry.read_registry().items()):
        if resource.no_own_terms:
            continue
        if prefix in SKIP:
            tqdm.write(f"skipping {prefix} because {SKIP[prefix]}")
            continue
        if skip_set and prefix in skip_set:
            tqdm.write(f"skipping {prefix} because in skip set")
            continue
        if skip_below is not None:
            if skip_below_inclusive:
                if prefix < skip_below:
                    continue
            else:
                if prefix <= skip_below:
                    continue
        has_pyobo = has_nomenclature_plugin(prefix)
        has_download = resource.has_download()
        if skip_pyobo and has_pyobo:
            continue
        if not has_pyobo and not has_download:
            continue
        yield prefix


def iter_helper_helper(
    f: Callable[[str, Unpack[GetOntologyKwargs]], X],
    use_tqdm: bool = True,
    skip_below: str | None = None,
    skip_pyobo: bool = False,
    skip_set: set[str] | None = None,
    **kwargs: Unpack[SlimGetOntologyKwargs],
) -> Iterable[tuple[str, X]]:
    """Yield all mappings extracted from each database given.

    :param f: A function that takes a prefix and gives back something that will be used
        by an outer function.
    :param use_tqdm: If true, use the tqdm progress bar
    :param skip_below: If true, skip sources whose names are less than this (used for
        iterative curation
    :param skip_pyobo: If true, skip sources implemented in PyOBO
    :param skip_set: A pre-defined blacklist to skip
    :param strict: If true, will raise exceptions and crash the program instead of
        logging them.
    :param kwargs: Keyword arguments passed to ``f``.

    :raises TypeError: If a type error is raised, it gets re-raised
    :raises urllib.error.HTTPError: If the resource could not be downloaded
    :raises urllib.error.URLError: If another problem was encountered during download
    :raises ValueError: If the data was not in the format that was expected (e.g., OWL)

    :yields: A prefix and the result of the callable ``f``
    """
    strict = kwargs.get("strict", True)
    prefixes = list(
        _prefixes(
            skip_set=skip_set,
            skip_below=skip_below,
            skip_pyobo=skip_pyobo,
        )
    )
    prefix_it = tqdm(
        prefixes, disable=not use_tqdm, desc=f"Building with {f.__name__}()", unit="resource"
    )
    for prefix in prefix_it:
        prefix_it.set_postfix(prefix=prefix)
        tqdm.write(
            click.style(f"\n{prefix} - {bioregistry.get_name(prefix)}", fg="green", bold=True)
        )
        try:
            yv = f(prefix, **kwargs)  # type:ignore
        except (UnhandledFormatError, NoBuildError) as e:
            # make sure this comes before the other runtimeerror catch
            logger.warning("[%s] %s", prefix, e)
        except urllib.error.HTTPError as e:
            logger.warning("[%s] HTTP %s: unable to download %s", prefix, e.getcode(), e.geturl())
            if strict and not bioregistry.is_deprecated(prefix):
                raise
        except urllib.error.URLError as e:
            logger.warning("[%s] unable to download - %s", prefix, e.reason)
            if strict and not bioregistry.is_deprecated(prefix):
                raise
        except ParseError as e:
            if not e.node:
                logger.warning("[%s] %s", prefix, e)
            else:
                logger.warning(str(e))
            if strict and not bioregistry.is_deprecated(prefix):
                raise e
        except RuntimeError as e:
            if "DrugBank" not in str(e):
                raise
            logger.warning("[drugbank] invalid credentials")
        except subprocess.CalledProcessError:
            logger.warning("[%s] ROBOT was unable to convert OWL to OBO", prefix)
        except ValueError as e:
            if _is_xml(e):
                # this means that it tried doing parsing on an xml page
                logger.warning(
                    "no resource available for %s. See http://www.obofoundry.org/ontology/%s",
                    prefix,
                    prefix,
                )
            else:
                logger.exception(
                    "[%s] got exception %s while parsing", prefix, e.__class__.__name__
                )
        except zipfile.BadZipFile as e:
            # This can happen if there's an error on UMLS
            logger.exception("[%s] got exception %s while parsing", prefix, e.__class__.__name__)
        except TypeError as e:
            logger.exception("[%s] got exception %s while parsing", prefix, e.__class__.__name__)
            if strict:
                raise e
        else:
            yield prefix, yv


def _is_xml(e) -> bool:
    return str(e).startswith("Tag-value pair parsing failed for:") or str(e).startswith(
        'Tag-value pair parsing failed for:\n<?xml version="1.0" encoding="UTF-8"?>'
    )


def _prep_dir(directory: None | str | pathlib.Path) -> pathlib.Path:
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
    it: Iterable[tuple[Any, ...]],
    db_name: str,
    columns: Sequence[str],
    *,
    directory: None | str | pathlib.Path = None,
    strict: bool = False,
    use_gzip: bool = True,
    summary_detailed: Sequence[int] | None = None,
) -> list[pathlib.Path]:
    """Help output database builds.

    :param f: A function that takes a prefix and gives back something that will be used
        by an outer function.
    :param db_name: name of the output resource (e.g., "alts", "names")
    :param columns: The names of the columns
    :param directory: The directory to output everything, or defaults to
        :data:`pyobo.constants.DATABASE_DIRECTORY`.
    :param strict: Passed to ``f`` by keyword

    :returns: A sequence of paths that got created.
    """
    start = time.time()
    directory = _prep_dir(directory)

    c: typing.Counter[str] = Counter()
    c_detailed: typing.Counter[tuple[str, ...]] = Counter()

    if use_gzip:
        db_path = directory.joinpath(f"{db_name}.tsv.gz")
    else:
        db_path = directory.joinpath(f"{db_name}.tsv")
    db_sample_path = directory.joinpath(f"{db_name}_sample.tsv")
    db_summary_path = directory.joinpath(f"{db_name}_summary.tsv")
    db_summary_detailed_path = directory.joinpath(f"{db_name}_summary_detailed.tsv")
    db_metadata_path = directory.joinpath(f"{db_name}_metadata.json")
    rv: list[tuple[str, pathlib.Path]] = [
        ("Metadata", db_metadata_path),
        ("Data", db_path),
        ("Sample", db_sample_path),
        ("Summary", db_summary_path),
    ]

    logger.info("writing %s to %s", db_name, db_path)
    logger.info("writing %s sample to %s", db_name, db_sample_path)
    sample_rows = []

    with safe_open_writer(db_path) as writer:
        # for the first 10 rows, put it in a sample file too
        with safe_open_writer(db_sample_path) as sample_writer:
            # write header
            writer.writerow(columns)
            sample_writer.writerow(columns)

            for row, _ in zip(it, range(10), strict=False):
                c[row[0]] += 1
                if summary_detailed is not None:
                    c_detailed[tuple(row[i] for i in summary_detailed)] += 1
                writer.writerow(row)
                sample_writer.writerow(row)
                sample_rows.append(row)

        # continue just in the gzipped one
        for row in it:
            c[row[0]] += 1
            if summary_detailed is not None:
                c_detailed[tuple(row[i] for i in summary_detailed)] += 1
            writer.writerow(row)

    with safe_open_writer(db_summary_path) as summary_writer:
        summary_writer.writerows(c.most_common())

    if summary_detailed is not None:
        logger.info(f"writing {db_name} detailed summary to {db_summary_detailed_path}")
        with safe_open_writer(db_summary_detailed_path) as detailed_summary_writer:
            detailed_summary_writer.writerows((*keys, v) for keys, v in c_detailed.most_common())
        rv.append(("Summary (Detailed)", db_summary_detailed_path))

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

    elapsed = time.time() - start
    click.secho(f"\nWrote the following files in {elapsed:.1f} seconds\n", fg="green")
    click.secho(indent(tabulate(rv), " "), fg="green")

    click.secho("\nSample rows:\n", fg="green")
    click.secho(indent(tabulate(sample_rows, headers=columns), " "), fg="green")
    click.echo()

    return [path for _, path in rv]
