# -*- coding: utf-8 -*-

"""Extract Selventa terminology information."""

import pandas as pd
from pyobo.normalizer import OboNormalizer

BASE = 'https://raw.githubusercontent.com/OpenBEL/resource-generator/master/datasets'
SCHEM_URL = f'{BASE}/selventa-legacy-chemical-names.txt'
SDIS_URL = f'{BASE}/selventa-legacy-diseases.txt'


def get_schem_df():
    df = pd.read_csv(SCHEM_URL, skiprows=8, sep='\t')
    for k in ('ALTIDS', 'TYPE'):
        del df[k]
    return df


def get_sdis_df():
    df = pd.read_csv(SDIS_URL, skiprows=9, sep='\t')
    for k in ('ALTIDS',):
        del df[k]
    # Type actually says if process or disease
    return df


def main():
    df = get_schem_df()
    print(*df.columns, sep='\n')
    print(df.head(3).transpose())
    n = OboNormalizer('chebi')
    for schem_id, label, xref in df[['ID', 'LABEL', 'XREF']].values:
        if pd.isna(xref):
            a, b, c = n.normalize(label)
            if a is None:
                continue
            print(schem_id, label, a, b, c)
        # else:
        #    print(schem_id, label, normalize_curie(xref))


if __name__ == '__main__':
    main()
