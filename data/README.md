# Data provenance

**Daqing Chen (2012), Online Retail II**, UCI Machine Learning Repository.
DOI: https://doi.org/10.24432/C5CG6D
Dataset: https://archive.ics.uci.edu/dataset/502/online+retail+ii
License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The source has 1,067,371 transaction rows from one UK online retailer, December
2009 to December 2011. It is historical giftware/wholesale activity, not Trent,
Westside, Zudio, or a modern Indian retail dataset. `UK_ONLINE` is a single
channel identifier; countries are customer markets, not stores.

Download with the documented CLI command. The original workbook is excluded
from git. Generated reports contain transformed aggregates and acknowledge
this source. `provenance.json` records the input SHA-256 and cleaning audit.
The `--demo` option produces clearly labelled synthetic data for fast tests;
it does not reproduce the public-data results.
