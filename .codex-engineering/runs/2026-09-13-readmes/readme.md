# RWA folder documentation validation

This run replaces seven unfinished RWA guides, including the CURVE and NSS
README files shown in the user's screenshots. It also updates the RWA and
Experimental navigation and source-guide links. No analytical source or
historical CSV was modified.

`validation.json` records the link, shell-syntax, assembly and consumer checks.
`rebuild-fixture.log` is output from the actual parameter-rebuild implementation
using isolated synthetic files. The exact Python recipe in the CURVE README was
extracted and executed with a fixture directory as its working directory.

Checks covered eight maturities and all three parameters, differing dates and row
orders, an unnamed CSV index, missing warmup values, rejection of duplicate dates,
missing dates and missing columns before curve output, and the current rebuild's
filenames and six-column output schema. The fixture's mu/theta curves were passed
unchanged to the rebuild; this documentation check did not refit NS/NSS models.

The documentation pass checked 66 relative links and 14 shell blocks across the
11 changed guide/instruction files with no failures. The actual nonlinear repair
and hierarchy implementations were unchanged; their existing regression evidence
is retained in the other dated runs. Scratch fixtures and extracted example code
stay under the ignored `tmp/` directory. See the [journal](../../JOURNAL.md) for
scope, the prior coverage error and the updated recurring workflow.
