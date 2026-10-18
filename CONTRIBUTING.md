# Contributing to V-Twin

Read the [product scope](docs/product-scope.md), [architecture](docs/architecture/README.md), and [development commands](docs/development.md) before changing the numerical or application boundaries. Select a roadmap issue and check its acceptance criteria and dependencies.

Install from the lockfiles, work on a short-lived branch, and keep changes focused on the selected issue. Run the Python quality report, pytest, the analytical check, and the frontend checks listed in the development guide. A numerical change should include a relevant analytical, conservation, convergence, or independently observed reference; matching the implementation with itself is not validation.

Describe the resulting behavior and its tests in the pull request. Link changed model assumptions, parameter sources, schemas, and ADRs where relevant. Label synthetic/example data explicitly. Do not claim physical wear accuracy or a performance target from the foundation checks alone.

Commit source, examples, configuration, and intentional lockfile changes. Keep environments, build outputs, generated reports, credentials, acquired private datasets, and large result files out of Git. After changing dependencies, regenerate the appropriate lockfile, inspect the diff, and run the affected checks before pushing.
