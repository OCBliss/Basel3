# Verified yield acquisition and domain integration

This milestone completes live FRED retrieval through cleaning, calibration and
parameter simulation. The source now uses three stable domains: data, calibration
and models. Start with the [source map](../../../src/RWA/readme.md) or
[live pipeline](../../../pipeline/rwa_live/readme.md).

## Completed run and tests

- [Full regression suite](full-suite.log): **186 tests passed in 44.087 seconds**.
- [Acquisition tests](acquisition-tests.log): 37 checks, including the actual model
  CLI, corruption rejection, bounded HTTP retries and raw-to-clean verification.
- [Actual live manager log](live-manager.log) and [configuration](live-config.yaml):
  both acquisition and hierarchy completed on live FRED input. Eight maturities,
  4,354 common observations from 2010-01-04 through 2026-09-10; 4,040 first-pass
  rows, 6,096 second-pass rows, 256 paths and 20 forecast increments.
- [Acquisition manifest](acquisition-manifest.json) and [model manifest](model-manifest.json)
  preserve quality, settings, hashes and input provenance. Original live artifacts
  remain locally under RWA/FRED/snapshots/2026-09-13-live and
  RWA/Experimental/HIERARCHY/2026-09-13-live. These large run directories are ignored.

Reproduction: follow the repository-local temporary-directory setup in the
[test guide](../../../tests/readme.md), then run `python3 -B -m unittest discover -s tests -v`.
For a new live run, follow the pipeline guide and choose new snapshot/output
names. The evidence configuration records an already completed run and therefore
must have those destinations changed before execution.

## Hypothesis, alternatives and findings

Preserving raw quotes, constraining causal fills and validating provenance makes
acquisition auditable before the estimated mu/theta/sigma histories are modeled.
[Alternatives](alternatives.json) compare filled and observed-only rate-increment
distributions using the repository's square-root JSD convention with natural logs
and 50/100/200 shared bins per maturity. Each live tenor has 179 imputed quotes.
For the ten-year series, the zero-increment fraction is 11.56% after filling versus
7.76% after dropping missing quotes; square-root JSD is approximately 0.0455.
Neither result establishes a superior cleaning policy. Dropping rows also leaves
irregular elapsed-time transitions, which the current fixed-dt model does not
represent. Preserve imputation flags for further model research.

The [historical DGS30 response](historical-DGS30.csv) contains 994 numeric quotes
in 1,038 rows during the 2002–2006 discontinuation described in
[FRED's notes](https://fred.stlouisfed.org/series/DGS30). Its maximum observed quote
gap is four calendar days. The reason for that populated response is not
established. An initial inference of an observed multi-year missing gap was
incorrect and withdrawn. Long-gap rejection is instead demonstrated with an
explicit synthetic case retained in alternatives.json.

A keyless [FRED graph download](https://fredhelp.stlouisfed.org/fred/data/downloading/using-the-download-data-link/)
was selected and tested. The bulk endpoint may ignore requested bounds; filtering
is enforced locally. The [REST observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)
requires a key and offers real-time controls. Current downloads restricted to
past observation dates are not historical real-time vintages.

## Failure iteration and architecture

The first live attempt stopped before subprocess execution because the new YAML
used the reverse dependency direction. It was corrected to the manager's existing
upstream-to-dependent convention, then the complete live run passed. Independent
parser review found short rows and NUL-contaminated tokens could be misread by the
initial pandas parser. Strict CSV record validation and control-character rejection
now cover both. Tests further drove strict boolean/integer schema checks and
verification that processed values are reproducible from preserved raw bytes,
even if an altered processed file's manifest hash is rewritten.

The previous flat task-oriented components were regrouped into data/parameters,
calibration/yields, calibration/curves and models/parameter_hierarchy; new retrieval
belongs in data/yields. Imports, root discovery, YAML, consumers and documentation
were moved together. Exactly three domains remain at the RWA source top level.

The existing schedule was independently verified ACTIVE every two hours; TOML
and scheduler DB agreed, with next run recorded at 2026-09-13 approximately
17:01 PDT when checked. No replacement, duplicate or cadence mutation was made.
