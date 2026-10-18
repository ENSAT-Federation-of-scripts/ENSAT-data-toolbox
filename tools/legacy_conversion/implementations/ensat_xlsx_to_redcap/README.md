# ENSAT XLSX to REDCap Converter

## Overview

This implementation provides a Python-based workflow for translating data from the historical ENS@T registry XLSX structure into a REDCap-compatible common data element format.

It represents one conversion approach within the broader ENSAT Data Toolbox and Federation of Scripts framework.

## Implementation

The converter reads historical ENS@T registry data distributed across multiple tumour-specific Excel worksheets and generates a standardized CSV output suitable for subsequent REDCap workflows.

The implementation includes mappings for major adrenal tumour domains and incorporates logic for identification, clinical variables, biomaterial information, tumour-specific variables, and follow-up information.

## Requirements

- Python 3
- pandas
- NumPy
- openpyxl

## Usage

```bash
python ensat_xlsx_to_redcap.py input.xlsx output.csv
