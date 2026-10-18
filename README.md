# ENSAT Data Toolbox

## Federation of Scripts for the Federation of Data

The **ENSAT Data Toolbox** is the software and methods repository supporting the broader **Federation of Data** concept for adrenal tumour research.

The central idea of the Federation of Data is that data generated across different centres, projects, time periods, database structures, and variable versions should remain interoperable, traceable, and reusable without requiring all participating centres to use one identical local technical solution.

The **Federation of Scripts** represents the practical software layer supporting this model.

It provides reproducible tools for understanding, transforming, harmonising, migrating, and versioning data so that heterogeneous local datasets can be aligned with a common ENS@T variable architecture.

---

## Federation of Data

The Federation of Data framework is designed to support distributed adrenal tumour research in which:

- participating centres may maintain their own local datasets and technical environments
- historical and contemporary datasets may use different variable names, structures, coding systems, and formats
- the common data model may evolve over time
- previously collected data must remain recoverable when variables are renamed, moved, redefined, split, merged, or retired
- semantic meaning and provenance should be preserved during data transformation
- data should be mapped toward a shared and interoperable variable structure

The aim is therefore not simply to move data from one spreadsheet to another.

The aim is to create a reproducible framework through which heterogeneous adrenal tumour data can be interpreted, mapped, transformed, updated, and reused within an evolving **Federation of Data**.

---

## Federation of Scripts

The Federation of Scripts is the technical toolbox supporting the Federation of Data.

This repository will contain reusable tools, mappings, documentation, and examples for three main tasks:

### 1. Variable Version Tracking

The common ENS@T variable structure may change over time.

The version-tracking tools will compare different versions of the L1–L4 variable catalogue and identify changes such as:

- unchanged variables
- renamed variables
- variables moved between L1, L2, L3, or L4
- newly introduced variables
- retired variables
- changes in datatype
- changes in units
- changes in permissible values
- changes in semantic definition
- split variables
- merged variables

The objective is to make changes in the evolving data model explicit and machine-readable.

---

### 2. Data Migration and Recovery

Changes in the variable model should not result in loss of previously collected data.

Migration tools will therefore support the recovery and transfer of existing values when a variable changes between versions.

For example:

`date_of_surgery`

may exist in both L2 and L3 in one version of the data model and later be consolidated into L2.

The migration workflow should:

1. identify the structural change
2. determine whether the variables represent the same clinical concept
3. locate previously collected values
4. identify duplicate or conflicting values
5. migrate or recover the appropriate data
6. validate the resulting dataset
7. preserve a transparent audit trail

This allows the Federation of Data to evolve without disconnecting new variable definitions from historical patient data.

---

### 3. Legacy ENS@T Data Conversion

Historical ENS@T datasets were created over many years and may differ substantially from the contemporary data model.

Conversion tools will support transformation of historical datasets into the current **L1–L4 architecture**.

The intended workflow is:

**Legacy ENS@T data**

→ variable identification and profiling

→ semantic interpretation

→ mapping to the appropriate L1–L4 variable

→ semantic and ontology mapping

→ transformation of values, units, and coding

→ validation

→ standardized output suitable for integration into the Federation of Data

Each conversion should retain the relationship between the original variable and the final standardized variable.

---

## L1–L4 Variable Architecture

The common variable model is organised into four levels:

- **L1** — local identifiers and pseudonymisation-related variables
- **L2** — shared/common data elements
- **L3** — adrenal disease-specific variables and instruments
- **L4** — project-specific variables

The Federation of Scripts will support both:

- conversion of historical variables into the L1–L4 model
- migration of data when the L1–L4 model itself changes over time

---

## Variable Identification and Semantic Mapping

A central component of the Federation of Data is understanding what a variable actually represents.

Legacy variables cannot always be mapped reliably using the variable name alone.

The conversion workflow should therefore evaluate information such as:

- original variable name
- variable label
- datatype
- units
- permissible values
- observed values
- timing
- clinical context
- repeated-measure structure
- related variables
- source project
- source year or database version

The resulting interpretation can then be used to determine the most appropriate target variable.

Where appropriate, standardized variables may additionally be linked to:

- controlled terminology
- ontology concepts
- semantic definitions
- interoperability standards such as OMOP or FHIR
- other relevant biomedical vocabularies

The objective is to preserve not only the value of a variable, but also its **meaning**.

---

## Variable Definition Space

The Federation of Data is supported by an evolving **Variable Definition Space**.

Each standardized variable can be represented together with metadata describing:

- variable definition
- L1–L4 location
- datatype
- units
- permissible values
- clinical context
- dependencies
- provenance
- semantic relationships
- ontology mappings
- transformation rules
- version history

This creates a structured environment in which variables can be compared, connected, reused, updated, and harmonised across projects.

---

## Human-Supervised and AI-Assisted Conversion

AI-assisted methods may be used to support:

- variable identification
- semantic interpretation
- source-to-target mapping
- generation of Python transformation code
- explanation of how target variables are constructed

However, automated mappings should remain transparent and reviewable.

For each transformed variable, the conversion process should be able to explain:

- which source variable or variables were used
- which target variable was created
- which transformation rule was applied
- why the variables were considered semantically equivalent
- whether units or coding were transformed
- whether ontology or terminology mappings were assigned

Clinical and data-domain review remains an essential component of the workflow.

---

## Repository Structure

The repository will progressively contain:

`tools/`  
Reusable scripts for version tracking, migration, recovery, and conversion.

`schemas/`  
Versions of the L1–L4 variable architecture.

`mappings/`  
Variable crosswalks, semantic mappings, ontology mappings, and transformation rules.

`projects/`  
Project-specific implementations organised by project and year.

`examples/`  
Synthetic examples demonstrating conversion and migration scenarios.

`docs/`  
Documentation of the Federation of Data methodology and technical architecture.

`tests/`  
Testing and validation resources.

---

## Initial Development Use Case

The first development use case will focus on:

`date_of_surgery`

This variable currently provides a useful example of overlap between L2 and L3.

It will be used to demonstrate how the Federation of Scripts can:

- identify duplicate or overlapping variable definitions
- compare different versions of the data model
- detect movement between L1–L4 levels
- preserve previously collected values
- generate an explicit migration rule
- document the resulting change

---

## Research Software Status

The ENSAT Data Toolbox is research software under active development.

Individual scripts may represent prototypes or specific migration solutions and should not automatically be assumed to have been validated across all historical ENS@T datasets, REDCap implementations, centres, projects, or variable versions.

Outputs should therefore be reviewed and validated before use in production research databases.

---

## Data Protection

The repository is intended to contain:

- software
- data-model definitions
- mapping specifications
- synthetic examples
- documentation
- validation resources

Patient-level clinical data should not be committed to the repository.

---

## Overall Concept

The relationship between the components can be summarised as:

**Federation of Data**

→ shared conceptual and semantic framework

→ evolving L1–L4 variable architecture

→ Variable Definition Space

→ Federation of Scripts

→ variable version tracking

→ migration and recovery of historical values

→ legacy ENS@T data conversion

→ semantically harmonised and reusable distributed research data

The objective is to allow the data model to evolve while preserving the connection between historical data, current definitions, and future research projects.
