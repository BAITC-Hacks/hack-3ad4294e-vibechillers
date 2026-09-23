# Function Lineage Auditor

Kazakhtelecom Track 11: compare organisational regulations before and after a
reorganisation, identify potentially lost or duplicated functions, and produce
a conclusion linked to source clauses.

## Project documents

- [Task text](seeds/kt/TASK.md)
- [Stage 1 plan, shared data contract and team modules](docs/plan.md)
- [Active Stage 2 plan, ownership and architecture decisions](docs/stage-2.md)
- [Architecture](docs/architecture.md)
- [Launch procedure and recorded limitations](docs/evidence/kt-launch.md)
- [Demo script](docs/demo.md)
- [Business case and assumptions](docs/business-case.md)
- [Development progress](docs/PROGRESS.md)

## Sources and infrastructure

The case consists of editions 8 and 9 of an anonymised internal-audit regulation.
[The manifest](seeds/kt/manifest.json) records provenance, hashes and the
organiser-provided material's hackathon-use restriction.

The repository includes a pre-built infrastructure kit: document ingestion,
retrieval, agent transport, SQLite persistence and a web shell. Track-specific
audit logic is separate from that infrastructure; the kit's interfaces remain
documented in [CONTRACT.md](CONTRACT.md). Historical kit build notes and synthetic
retrieval scores are not evidence of this case's audit quality.

The repository's code licence is [MIT](LICENSE); case-material restrictions are
listed separately in the manifest.
