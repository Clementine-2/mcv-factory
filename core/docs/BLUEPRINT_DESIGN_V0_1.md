# Blueprint Design V0.1

## Purpose

Project Blueprint is the stable intermediate representation between user/project requirements and specific profiles, formulas, capabilities, providers, scaffolding, and harnesses.

## Universal core

Required:

- `schema_version`
- `project.purpose`
- at least one `work_products[*].kind`

Optional common semantics:

- targets
- technology required/preferred/prohibited
- lifecycle
- scope scale hint
- hard and quality constraints
- flat components
- registered domain extensions

## Key exclusions

Blueprint does not contain:

- current task
- current Git branch/commit
- current test status
- Agent session/messages/roles
- selected Harness/Runner/scaffolder/spec framework
- selected testing framework or concrete commands
- checkpoint contents
- build logs
- secrets or credentials

## Components

Components are optional and flat in V0.1. They cannot recursively contain `components`.

## Extensions

Extensions are namespaced domain semantics. Provider configuration is not a Blueprint extension.

## Provenance sidecar

`project.blueprint.meta.yaml` carries provenance, assumptions, and unresolved information separately from the human-readable main Blueprint.

Frozen provenance classes:

- EXPLICIT
- INFERRED
- DETECTED
- DEFAULT

## Unknown semantics

Unknown optional fields are normally omitted. Important missing information is recorded in metadata `unresolved` entries.

P1.2 adds `resolution_required` to distinguish:

- advisory unresolved -> `USABLE`
- must resolve before composition -> `NEEDS_RESOLUTION`
- safety/logical stop -> `BLOCKED`
