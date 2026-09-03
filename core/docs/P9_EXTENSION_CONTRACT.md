# P9 Extension Contract

Status: frozen candidate for P9 closeout.
Factory version: 0.10.0.
Extension API: 1.

## Purpose

P9 makes Project Factory extensible without turning Core into a package manager, marketplace, Harness, MCP server, or arbitrary plugin loader. Extensions are explicit project-factory composition inputs. They never become Blueprint facts merely because Factory uses them.

## Two trust classes

### Declarative

A declarative extension may contribute validated, namespaced registry records and scoped project artifacts. It may compose existing trusted Providers and Recipes. It may not introduce a new executable Provider or load Python code.

### Trusted code

A trusted-code extension may register typed Formula adapters, scaffold Recipes, Verification builders, and Migration hooks through the `project_factory.extensions` PyPA entry-point group. Enabling trusted code means trusting the installed Python distribution itself. Project Factory does not sandbox it, sign it, install it, or guarantee its provenance.

Trusted code is never loaded merely because metadata was discovered. The Extension Set must explicitly register it with `trusted-code` trust.

## Extension Manifest

The manifest is versioned and schema validated. P9 requires:

- extension id and version;
- mode (`declarative` or `trusted-code`);
- exact Factory extension API `1`;
- namespaced Registry contribution ids;
- safe project artifact source/target paths;
- for trusted code, exact distribution name/version and entry-point identity.

Project artifacts are confined to:

`.project/extensions/<extension-id>/...`

## Extension Set

The Extension Set is explicit external state. Registration changes use:

`DryRun plan -> exact plan SHA256 -> Apply`

Supported state operations are add, enable, disable, and remove. `remove` only unregisters the extension from Factory state. It does not delete extension source or uninstall a Python distribution.

## Supply-chain receipt

For enabled trusted-code extensions, P9 fingerprints only stable publisher/package content belonging to that extension distribution according to Python distribution metadata. Installer/runtime by-products such as `direct_url.json`, `INSTALLER`, `REQUESTED`, rewritten `RECORD`, and `__pycache__`/bytecode are excluded so an equivalent reinstall does not create a false drift alarm. It does not perform a whole-machine or whole-environment hash.

The project lock records:

- extension id/version/mode/trust;
- manifest SHA256;
- contribution SHA256;
- distribution name/version;
- bounded distribution SHA256 and file count;
- entry-point identity;
- materialized extension artifact hashes.

If a trusted distribution changes content without changing extension version, Factory refuses re-verification or upgrade as same-version code/content drift.

## Runtime registration

Trusted code receives a typed registrar. P9 supports these handler classes:

- Formula adapters;
- scaffold Recipes;
- Verification builders;
- Migration hooks.

Handler ids must be namespaced by extension id. Duplicate handler contributions fail closed.

## Migration

Existing-project migration does not implicitly install newly enabled extensions. An extension present in Project Lock must also be present in the supplied Extension Set.

When an extension version changes, its trusted Migration hook may only return targets under:

`.project/extensions/<extension-id>/...`

Targets outside that namespace are rejected before Apply. The normal P8 DryRun, plan hash, local rollback point, postimage guard, Verification and rollback rules still apply.

## Escapeability

Extensions may materialize Factory-owned metadata/resources, but extension executable code is not copied into the business source tree. Removing Factory metadata may remove Factory conveniences, but the generated native project must remain fundamentally buildable/developable according to the existing Escapeability rule.

## Explicit non-goals

P9 does not provide:

- automatic package download/install/update;
- automatic source deletion on unregister;
- extension marketplace/catalog;
- signature or publisher reputation infrastructure;
- sandboxing of trusted Python code;
- dependency solver;
- arbitrary shell commands in declarative manifests;
- Host/Harness plugin loading;
- automatic extension migration without DryRun/confirmation.

## Upstream mechanism choice

PyPA entry points are used for trusted Python plugin discovery rather than inventing a private code-discovery format. Spec Kit's independently versioned manifest-style extensions were also used as a design reference for keeping extensions self-contained and out of Core. Project Factory does not copy or fork either upstream implementation.
