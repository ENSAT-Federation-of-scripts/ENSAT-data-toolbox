# ENSAT Data Toolbox

Research software toolkit for versioning, harmonisation, migration, and conversion of ENS@T adrenal tumour data across evolving L1–L4 data models.

## Purpose

The ENSAT Data Toolbox is a research software repository designed to support the evolution, harmonisation, and migration of adrenal tumour data within the ENS@T data ecosystem.

The repository will provide tools for:

- tracking changes between different versions of the L1–L4 variable structure
- identifying renamed, moved, added, retired, or modified variables
- recovering and migrating previously collected REDCap values when the data model changes
- converting historical ENS@T datasets into the current L1–L4 structure
- documenting semantic definitions, ontology mappings, transformation rules, and provenance
- generating auditable outputs for data migration and harmonisation

## Main Tool Families

### 1. Variable Version Tracking

Compare different versions of the ENS@T L1–L4 variable catalogue and identify structural or semantic changes.

Examples include:

- variable renamed
- variable moved from L3 to L2
- permissible values changed
- datatype changed
- variable added or retired
- variables split or merged

### 2. Data Migration and Recovery

Preserve and recover previously collected values when the variable structure changes.

Example:

`date_of_surgery` exists in both L2 and L3 in one version of the data model and is subsequently consolidated into L2.

The migration workflow should identify the change, recover historical values, detect conflicts, migrate the data, and preserve an audit trail.

### 3. Legacy ENS@T Data Conversion

Convert historical ENS@T datasets into the contemporary L1–L4 structure.

The intended workflow is:

Legacy data → variable identification → semantic interpretation → L1–L4 mapping → ontology/semantic mapping → transformation → validation → standardized output.

## Status

Repository architecture and documentation are currently under development.

The first development use case will focus on variable versioning and migration using `date_of_surgery` as an example.
