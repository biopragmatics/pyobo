# -*- coding: utf-8 -*-

"""Convert the UniProt Subcellular Locations Controlled vocabulary.

Notes from UniProt on line codes:

---------  -------------------------------   ----------------------------
Line code  Content                           Occurrence in an entry
---------  -------------------------------   ----------------------------
ID         Identifier (location)             Once; starts an entry
IT         Identifier (topology)             Once; starts a 'topology' entry
IO         Identifier (orientation)          Once; starts an 'orientation' entry
AC         Accession (SL-xxxx)               Once
DE         Definition                        Once or more
SY         Synonyms                          Optional; Once or more
SL         Content of subc. loc. lines       Once
HI         Hierarchy ('is-a')                Optional; Once or more
HP         Hierarchy ('part-of')             Optional; Once or more
KW         Associated keyword (accession)    Optional; Once
GO         Gene ontology (GO) mapping        Optional; Once or more
AN         Annotation note                   Optional; Once or more
RX         Interesting references            Optional; Once or more
WW         Interesting links                 Optional; Once or more
//         Terminator                        Once; ends an entry
"""

URL = 'https://www.uniprot.org/docs/subcell.txt'
