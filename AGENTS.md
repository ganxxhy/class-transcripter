# Engineering rules

- Write all new source code, identifiers, filenames, technical comments, docstrings and tests in English.
- Keep existing public interfaces, persisted JSON keys, MCP tool names and user-facing translations compatible. Do not rename them without a migration plan.
- Domain code must not depend on infrastructure or presentation. Inject dependencies into application services; wire concrete adapters at composition roots.
- Add regression tests for changed behavior. Run existing tests and Windows/Linux packaging checks before merging.
- Never commit secrets or user data. Do not merge or publish releases without maintainer approval.
