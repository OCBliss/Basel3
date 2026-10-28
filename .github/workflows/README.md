# CallReports publication

`publish-callreports.yml` builds and validates the wheel and source distribution,
runs the independent package tests on the installed wheel, and uploads the
validated artifacts to PyPI. The publishing job uses PyPI Trusted Publishing;
no persistent PyPI token is stored in this repository.

The package owner's PyPI account must configure this pending publisher before
the first upload, or the corresponding project publisher after creation:

| Setting | Value |
| --- | --- |
| PyPI project | `CallReports` |
| GitHub owner | `OCBliss` |
| Repository | `Basel3` |
| Workflow filename | `publish-callreports.yml` |
| Environment | `pypi` |

After the publisher is configured, create a release tag matching the version in
`pyproject.toml`, for example `callreports-v0.1.0`, and push that tag. The workflow
also supports manual dispatch. Its build job has repository-read permission;
only the publishing job can request an identity token. The publisher's scope is
limited to the `CallReports` project on PyPI.

An existing PyPI version cannot be replaced. Review and increment the version
before a subsequent release; failed publication must be investigated rather
than silently skipped. After publication succeeds, verify the PyPI metadata and
install by name into a fresh environment:

```sh
python3 -m pip install --index-url https://pypi.org/simple CallReports
```

See PyPI's [pending publisher setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
and [publishing instructions](https://docs.pypi.org/trusted-publishers/using-a-publisher/).
