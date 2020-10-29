# -*- coding: utf-8 -*-

"""This script compares what's in OBO, OLS, and MIRIAM."""

import json
import os

import matplotlib.pyplot as plt
from matplotlib_venn import venn3

HERE = os.path.abspath(os.path.dirname(__file__))


def _get_json(name):
    with open(os.path.join(HERE, name)) as file:
        return json.load(file)


def main():
    """Compare the registries."""
    miriam = _get_json('miriam.json')
    miriam_entries = {
        entry['prefix'].lower()
        for entry in miriam
    }

    ols = _get_json('ols.json')
    ols_entries = {
        entry['ontologyId'].lower()
        for entry in ols
    }

    obofoundry = _get_json('obofoundry.json')
    obofoundry_entries = {
        entry['id'].lower()
        for entry in obofoundry
    }

    venn3(
        subsets=[miriam_entries, ols_entries, obofoundry_entries],
        set_labels=('MIRIAM', 'OLS', 'OBOFoundry'),
    )
    plt.tight_layout()
    plt.savefig('compare.svg')

    # nothing interesting unique to OLS
    # print(*sorted(ols_entries - miriam_entries - obofoundry_entries), sep='\n')
    # nothing interesting unique in OBO
    # print(*sorted(obofoundry_entries - miriam_entries - ols_entries), sep='\n')
    # Some things missing from miriam
    # print(*sorted(obofoundry_entries.union(ols_entries) - miriam_entries), sep='\n')

    # Stuff important enough to make it everywhere
    print(*sorted(set.intersection(ols_entries, miriam_entries, obofoundry_entries)), sep='\n')


if __name__ == '__main__':
    main()
