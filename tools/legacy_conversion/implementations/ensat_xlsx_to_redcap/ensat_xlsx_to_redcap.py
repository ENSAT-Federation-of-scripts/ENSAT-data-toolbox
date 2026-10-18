#!/usr/bin/env python3
"""
ENSAT Old Registry (XLSX) → New REDCap CDE Translator
======================================================

Translates patient data from the full ENSAT registry export format
(ensat_allparameters_empty_240425.xlsx) into the new ENSAT CDE REDCap
instrument format (instrument_ENSAT_CDE_250327.csv).

The old registry stores data across 65 sheets with tumour-type-specific
detail. The new CDE is a single flat instrument with 53 fields.

Usage:
    python ensat_xlsx_to_redcap.py input.xlsx output.csv

Requirements:
    pip install pandas openpyxl

Notes:
    - Fields marked [not exported] in the CDE (names, DOB, local ID) cannot
      be populated from the XLSX as it does not contain these identifiers.
    - Calculated fields (age_diagnosis, age_diagnosis_2, age_first_surgery_v1)
      are left blank as REDCap will compute them automatically from dates.
    - The script determines tumour type from which sheets contain data for
      each patient, since the XLSX has no explicit tumour type field.
    - Some CDE fields require clinical interpretation of detailed XLSX data
      (e.g., deriving PPGL secretion categories from raw lab values). These
      are marked with TODO comments where automated mapping is approximate.
"""

import sys
import warnings
import pandas as pd
import numpy as np
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


# =============================================================================
# 1. SHEET READING HELPERS
# =============================================================================

def read_sheet(xlsx_path, sheet_name):
    """Read a sheet, return DataFrame or empty DataFrame if sheet missing."""
    try:
        df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
        # Drop fully-null rows
        df = df.dropna(how="all")
        # Drop columns that are entirely null (padding columns from export)
        df = df.dropna(axis=1, how="all")
        return df
    except Exception:
        return pd.DataFrame()


def get_first_record(df, patient_id, id_col="patient_id"):
    """Get the first record for a patient from a repeating-instrument sheet."""
    if df.empty or id_col not in df.columns:
        return pd.Series(dtype=object)
    matches = df[df[id_col] == patient_id]
    if matches.empty:
        return pd.Series(dtype=object)
    return matches.iloc[0]


def get_last_record(df, patient_id, date_col=None, id_col="patient_id"):
    """Get the last record for a patient (by date if available, else last row)."""
    if df.empty or id_col not in df.columns:
        return pd.Series(dtype=object)
    matches = df[df[id_col] == patient_id]
    if matches.empty:
        return pd.Series(dtype=object)
    if date_col and date_col in matches.columns:
        matches = matches.sort_values(date_col, na_position="first")
    return matches.iloc[-1]


def patient_has_data(df, patient_id, id_col="patient_id"):
    """Check if a patient has any non-null data in a sheet (beyond just patient_id)."""
    if df.empty or id_col not in df.columns:
        return False
    matches = df[df[id_col] == patient_id]
    if matches.empty:
        return False
    # Check if any column other than patient_id has data
    other_cols = [c for c in matches.columns if c != id_col]
    return matches[other_cols].notna().any(axis=1).any()


def safe_val(series, col):
    """Safely extract a value from a Series, returning None if missing."""
    if isinstance(series, pd.Series) and col in series.index:
        v = series[col]
        if pd.isna(v):
            return None
        return v
    return None


# =============================================================================
# 2. TUMOUR TYPE DETECTION
# =============================================================================

def detect_tumour_type(patient_id, sheets):
    """
    Determine tumour type from which sheets contain data for this patient.
    Returns: 1=NAPACA, 2=PPGL, 3=ACC, 4=APA, 5=Other, or None
    """
    has_acc = any(
        patient_has_data(sheets.get(s, pd.DataFrame()), patient_id)
        for s in [
            "ACC_DiagnosticProcedures", "ACC_TumorStaging", "ACC_Surgery",
            "ACC_Pathology", "ACC_FollowUp",
        ]
    )
    has_pheo = any(
        patient_has_data(sheets.get(s, pd.DataFrame()), patient_id)
        for s in [
            "Pheo_PatientHistory", "Pheo_TumorDetails", "Pheo_Surgery",
            "Pheo_BiochemicalAssessment", "Pheo_FollowUp",
        ]
    )
    has_napaca = any(
        patient_has_data(sheets.get(s, pd.DataFrame()), patient_id)
        for s in [
            "NAPACA_DiagnosticProcedures", "NAPACA_Imaging",
            "NAPACA_Pathology", "NAPACA_FollowUp",
        ]
    )
    has_apa = any(
        patient_has_data(sheets.get(s, pd.DataFrame()), patient_id)
        for s in [
            "APA_PatientHistory", "APA_BiochemicalAssessment",
            "APA_Surgery", "APA_FollowUp",
        ]
    )

    if has_acc:
        return 3
    elif has_pheo:
        return 2
    elif has_napaca:
        return 1
    elif has_apa:
        return 4
    else:
        return None  # Could be 5 (Other) or truly unknown


# =============================================================================
# 3. FIELD-LEVEL MAPPING FUNCTIONS
# =============================================================================

def map_identification(patient_id, ident):
    """Map Identification sheet → CDE demographics."""
    row = get_first_record(ident, patient_id)
    result = {}

    result["record_id"] = patient_id
    result["center_v1"] = safe_val(row, "ensat_database")
    # first_name_v1, last_name_v1, local_patient_id_v1 → not available in XLSX
    result["first_name_v1"] = None
    result["last_name_v1"] = None
    result["local_patient_id_v1"] = None

    # Sex: XLSX values need mapping to CDE codes (0=Female, 1=Male, 2=N/A)
    sex = safe_val(row, "sex")
    if sex is not None:
        sex_str = str(sex).strip().lower()
        sex_map = {"female": 0, "f": 0, "0": 0, "male": 1, "m": 1, "1": 1}
        result["gender_v1"] = sex_map.get(sex_str, 2)
    else:
        result["gender_v1"] = None

    # DOB: XLSX only has year_of_birth; CDE wants full date
    yob = safe_val(row, "year_of_birth")
    if yob is not None:
        result["dob_v1"] = f"{int(yob)}-01-01"  # Approximate: Jan 1 of birth year
    else:
        result["dob_v1"] = None

    result["date_inclusion"] = safe_val(row, "record_date")

    return result


def map_general_clinical(patient_id, tumour_type, sheets):
    """Map diagnosis dates, follow-up, surgery status."""
    result = {}

    # --- Date of diagnosis ---
    diag_date = None
    if tumour_type == 3:  # ACC
        row = get_first_record(sheets.get("ACC_DiagnosticProcedures", pd.DataFrame()), patient_id)
        diag_date = safe_val(row, "date_of_diagnosis")
    elif tumour_type == 2:  # PPGL
        row = get_first_record(sheets.get("Pheo_PatientHistory", pd.DataFrame()), patient_id)
        diag_date = safe_val(row, "date_first_path_diagnosis")
    elif tumour_type == 1:  # NAPACA
        row = get_first_record(sheets.get("NAPACA_DiagnosticProcedures", pd.DataFrame()), patient_id)
        year = safe_val(row, "year_of_diagnosis")
        month = safe_val(row, "month_of_diagnosis")
        if year is not None:
            m = int(month) if month is not None else 1
            diag_date = f"{int(year)}-{m:02d}-01"
    elif tumour_type == 4:  # APA
        row = get_first_record(sheets.get("APA_PatientHistory", pd.DataFrame()), patient_id)
        year = safe_val(row, "year_of_diagnosis")
        if year is not None:
            diag_date = f"{int(year)}-01-01"

    result["date_diagnosis"] = diag_date
    # age_diagnosis → calculated by REDCap, leave blank
    result["age_diagnosis"] = None

    # --- Last follow-up ---
    fu_sheets_map = {
        3: ("ACC_FollowUp", "followup_date_1", "patient_status_1"),
        2: ("Pheo_FollowUp", "followup_date_1", "alive_1"),
        1: ("NAPACA_FollowUp", "followup_date_1", "followup_alive_1"),
        4: ("APA_FollowUp", "followup_date_1", "followup_alive_1"),
    }

    fu_date = None
    alive = None
    if tumour_type in fu_sheets_map:
        sheet_name, date_col, alive_col = fu_sheets_map[tumour_type]
        fu_df = sheets.get(sheet_name, pd.DataFrame())
        fu_row = get_last_record(fu_df, patient_id, date_col=date_col)
        fu_date = safe_val(fu_row, date_col)
        alive_raw = safe_val(fu_row, alive_col)
        if alive_raw is not None:
            # Normalise: CDE yesno → 1=Yes, 0=No
            alive_str = str(alive_raw).strip().lower()
            if alive_str in ("1", "yes", "true", "alive"):
                alive = 1
            elif alive_str in ("0", "no", "false", "dead", "deceased"):
                alive = 0

    result["date_lastfollowup_v1"] = fu_date
    result["age_diagnosis_2"] = None  # Calculated by REDCap
    result["vitalstatus_lastfollowup_v1"] = alive

    # --- Surgery ---
    surgery_sheets = {
        3: "ACC_Surgery",
        2: "Pheo_Surgery",
        1: "NAPACA_Surgery",
        4: "APA_Surgery",
    }
    has_surgery = False
    surgery_date = None
    if tumour_type in surgery_sheets:
        surg_df = sheets.get(surgery_sheets[tumour_type], pd.DataFrame())
        has_surgery = patient_has_data(surg_df, patient_id)
        if has_surgery:
            surg_row = get_first_record(surg_df, patient_id)
            date_col = "intervention_date" if tumour_type == 4 else "surgery_date_1"
            surgery_date = safe_val(surg_row, date_col)

    result["surgery_v1"] = 1 if has_surgery else 0
    result["date_first_surgery_v1"] = surgery_date
    result["age_first_surgery_v1"] = None  # Calculated by REDCap

    return result


def map_biomaterial(patient_id, tumour_type, sheets):
    """Map biomaterial availability from tumour-type-specific biomaterial sheets."""
    result = {}

    bio_sheets = {
        3: "ACC_Biomaterial",
        2: "Pheo_Biomaterial",
        1: "NAPACA_Biomaterial",
        4: "APA_Biomaterial",
    }

    bio_row = pd.Series(dtype=object)
    if tumour_type in bio_sheets:
        bio_df = sheets.get(bio_sheets[tumour_type], pd.DataFrame())
        bio_row = get_first_record(bio_df, patient_id)

    # Tumour biomaterial
    frozen = safe_val(bio_row, "tumor_tissue_frozen_1")
    paraffin = safe_val(bio_row, "tumor_tissue_paraffin_1")

    if frozen is not None or paraffin is not None:
        has_tumour_bio = any(
            safe_val(bio_row, c) not in (None, 0, "0", "No", "no")
            for c in ["tumor_tissue_frozen_1", "tumor_tissue_paraffin_1", "tumor_tissue_dna_1"]
            if c in bio_row.index
        )
        result["tumor_biomaterial_v1"] = 1 if has_tumour_bio else 2
    else:
        result["tumor_biomaterial_v1"] = 3  # Unknown

    # Tumour biomaterial type (checkbox: 1=Frozen, 2=Paraffin, 3=None)
    # REDCap checkboxes stored as tumor_biomaterial_type_v1___1, ___2, ___3
    frozen_val = safe_val(bio_row, "tumor_tissue_frozen_1")
    paraffin_val = safe_val(bio_row, "tumor_tissue_paraffin_1")
    result["tumor_biomaterial_type_v1___1"] = 1 if frozen_val not in (None, 0, "0", "No", "no") else 0
    result["tumor_biomaterial_type_v1___2"] = 1 if paraffin_val not in (None, 0, "0", "No", "no") else 0
    result["tumor_biomaterial_type_v1___3"] = (
        1 if result["tumor_biomaterial_type_v1___1"] == 0 and result["tumor_biomaterial_type_v1___2"] == 0 else 0
    )

    # Omic data → CDE only, no XLSX source
    for i in range(1, 7):
        result[f"tumor_omic_type_v1___{i}"] = 0

    # Blood/urine biomaterial
    plasma = safe_val(bio_row, "plasma_1")
    serum = safe_val(bio_row, "serum_1")
    urine_24h = safe_val(bio_row, "24h_urine_1")
    spot_urine = safe_val(bio_row, "spot_urine_1")
    leuk_dna = safe_val(bio_row, "leukocyte_dna_1")

    blood_urine_cols = ["plasma_1", "serum_1", "24h_urine_1", "spot_urine_1", "leukocyte_dna_1"]
    has_blood_urine = any(
        safe_val(bio_row, c) not in (None, 0, "0", "No", "no")
        for c in blood_urine_cols if c in bio_row.index
    )

    if any(c in bio_row.index for c in blood_urine_cols):
        result["bloodurine_biomaterial_v1"] = 1 if has_blood_urine else 2
    else:
        result["bloodurine_biomaterial_v1"] = 3  # Unknown

    # Blood/urine type (checkbox: 1=EDTA plasma, 2=Serum, 3=24h urine, 4=Spot urine, 5=PBMC, 6=Leukocyte DNA, 7=None)
    def is_yes(val):
        return val not in (None, 0, "0", "No", "no")

    result["bloodurine_biomaterial_type_v1___1"] = 1 if is_yes(plasma) else 0
    result["bloodurine_biomaterial_type_v1___2"] = 1 if is_yes(serum) else 0
    result["bloodurine_biomaterial_type_v1___3"] = 1 if is_yes(urine_24h) else 0
    result["bloodurine_biomaterial_type_v1___4"] = 1 if is_yes(spot_urine) else 0
    result["bloodurine_biomaterial_type_v1___5"] = 0  # PBMC: no direct XLSX column
    result["bloodurine_biomaterial_type_v1___6"] = 1 if is_yes(leuk_dna) else 0
    result["bloodurine_biomaterial_type_v1___7"] = (
        1 if not has_blood_urine else 0
    )

    # Blood/urine omic → CDE only, no XLSX source
    for i in range(1, 6):
        result[f"bloodurine_omic_type_v1___{i}"] = 0

    return result


def map_napaca(patient_id, sheets):
    """Map NAPACA-specific fields."""
    result = {}
    diag = get_first_record(
        sheets.get("NAPACA_DiagnosticProcedures", pd.DataFrame()), patient_id
    )
    img = get_first_record(
        sheets.get("NAPACA_Imaging", pd.DataFrame()), patient_id
    )

    # Incidentaloma
    incidental = safe_val(diag, "symptoms_incidental")
    if incidental is not None:
        inc_str = str(incidental).strip().lower()
        if inc_str in ("1", "yes", "true"):
            result["napaca_incidentaloma_v1"] = 1
        elif inc_str in ("0", "no", "false"):
            result["napaca_incidentaloma_v1"] = 2
        else:
            result["napaca_incidentaloma_v1"] = 3
    else:
        result["napaca_incidentaloma_v1"] = None

    # Secretion status (CDE: 1=Overt Cushing, 2=MACS, 3=Inactive, 4=Other, 5=Unknown)
    # Derive from XLSX diagnostic fields
    cushing = safe_val(diag, "cushings_syndrome")
    subclinical = safe_val(diag, "subclinical_cushing")

    if cushing is not None and str(cushing).strip().lower() in ("1", "yes", "true"):
        result["napaca_secretion_v1"] = 1  # Overt Cushing
    elif subclinical is not None and str(subclinical).strip().lower() in ("1", "yes", "true"):
        result["napaca_secretion_v1"] = 2  # MACS
    elif cushing is not None or subclinical is not None:
        result["napaca_secretion_v1"] = 3  # Inactive (neither flagged)
    else:
        result["napaca_secretion_v1"] = 5  # Unknown

    # Size (mm)
    size = safe_val(diag, "tumor_size")
    if size is None:
        # Try lateralised sizes from imaging
        left = safe_val(img, "left_adrenal_max_tumor_1")
        right = safe_val(img, "right_adrenal_max_tumor_1")
        sizes = [s for s in [left, right] if s is not None]
        size = max(sizes) if sizes else None
    result["napaca_size_v1"] = int(size) if size is not None else None

    # NAPACA type (CDE: 1-7) → approximate from NAPACA_Pathology.pathology_diagnosis_1
    # TODO: This requires mapping of pathology diagnosis text/codes to CDE categories.
    # Without knowing the exact coding used in the XLSX, we leave this for manual review.
    result["napaca_type_v1"] = None
    result["napaca_other_type_v1"] = None

    return result


def map_ppgl(patient_id, sheets):
    """Map PPGL-specific fields."""
    result = {}
    hist = get_first_record(
        sheets.get("Pheo_PatientHistory", pd.DataFrame()), patient_id
    )
    genetics = get_first_record(
        sheets.get("Pheo_Genetics", pd.DataFrame()), patient_id
    )
    tumour = get_first_record(
        sheets.get("Pheo_TumorDetails", pd.DataFrame()), patient_id
    )

    # Syndromic / germline predisposition
    # CDE: 1=NF1, 2=MEN2, 3=VHL, 4=Carney-Stratakis, 5=Multiple PPGL, 6=Other, 7=Isolated, 8=Not known
    gene_map = {
        "nf1": 1, "ret": 2, "vhl": 3, "sdhc": 4, "sdhd": 4, "sdhb": 5,
    }
    syndromic = None
    susc_gene = safe_val(hist, "susceptibility_gene")
    if susc_gene is not None:
        gene_lower = str(susc_gene).strip().lower()
        syndromic = gene_map.get(gene_lower, 6)
    else:
        susc_presence = safe_val(hist, "susceptibility_gene_presence")
        if susc_presence is not None:
            pres_str = str(susc_presence).strip().lower()
            if pres_str in ("0", "no", "false"):
                syndromic = 7  # Isolated
            elif pres_str in ("1", "yes", "true"):
                syndromic = 6  # Yes but gene unknown → Other
        else:
            syndromic = 8  # Not known

    result["ppgl_syndromic_v1"] = syndromic

    # Somatic mutations (checkbox: 1-7)
    # TODO: Mapping from per-gene XLSX fields to CDE cluster categories requires
    # clinical interpretation. We populate basic flags here.
    for i in range(1, 8):
        result[f"ppgl_mutation_v1___{i}"] = 0

    # Check if any somatic mutation detected across gene fields
    mutation_genes = []
    gene_fields = [
        ("vhl", "vhl_mutation_detected"), ("sdhd", "sdhd_mutation_detected"),
        ("sdhb", "sdhb_mutation_detected"), ("ret", "ret_mutation_detected"),
        ("nf1", "nf1_mutation_detected"), ("tmem127", "tmem127_mutation_detected"),
        ("max", "max_mutation_detected"), ("sdhc", "sdhc_mutation_detected"),
        ("sdha", "sdha_mutation_detected"), ("sdhaf2", "sdhaf2_mutation_detected"),
        ("fh", "fh_mutation_detected"), ("epas1", "epas1_mutation_detected"),
        ("mdh2", "mdh2_mutation_detected"),
    ]
    for gene_name, field in gene_fields:
        val = safe_val(genetics, field)
        if val is not None and str(val).strip().lower() in ("1", "yes", "true"):
            mutation_genes.append(gene_name)
            result["ppgl_mutation_v1___1"] = 1  # A somatic mutation identified

    # Mutation name
    gene_names = []
    for gene_name, field in gene_fields:
        name_field = field.replace("_detected", "_name")
        name_val = safe_val(genetics, name_field)
        if name_val is not None:
            gene_names.append(str(name_val))
    result["ppgl_mutation_name_v1"] = " ".join(gene_names) if gene_names else None

    # Location (checkbox: 1=Adrenal, 2=Extra-adrenal, 3=Head/neck, 4=Not known)
    for i in range(1, 5):
        result[f"ppgl_location_v1___{i}"] = 0

    site = safe_val(tumour, "tumor_site_1")
    a_or_e = safe_val(tumour, "tumor_a_or_e_1")
    if a_or_e is not None:
        ae_str = str(a_or_e).strip().lower()
        if ae_str in ("a", "adrenal", "1"):
            result["ppgl_location_v1___1"] = 1
        elif ae_str in ("e", "extra-adrenal", "extra", "2"):
            result["ppgl_location_v1___2"] = 1
    elif site is not None:
        site_str = str(site).strip().lower()
        if "adrenal" in site_str and "extra" not in site_str:
            result["ppgl_location_v1___1"] = 1
        elif "head" in site_str or "neck" in site_str:
            result["ppgl_location_v1___3"] = 1
        else:
            result["ppgl_location_v1___2"] = 1

    # Diameter
    size = safe_val(tumour, "pathology_tumor_size_largest_1")
    if size is None:
        size = safe_val(tumour, "largest_size_x_1")
    result["ppgl_diameter_v1"] = int(size) if size is not None else None

    # Secretion (checkbox: 1-8)
    # TODO: Requires interpretation of quantitative Pheo_BiochemicalAssessment data
    # against normal ranges to categorise. Left blank for manual review.
    for i in range(1, 9):
        result[f"ppgl_secretion_v1___{i}"] = 0

    # Metastases
    mets = safe_val(tumour, "tumor_distant_metastases_1")
    disease_met = safe_val(
        get_first_record(sheets.get("Pheo_PatientHistory", pd.DataFrame()), patient_id),
        "disease_metastatic"
    )
    if mets is not None and str(mets).strip().lower() in ("1", "yes", "true"):
        result["ppgl_metastases_v1"] = 1  # Metastatic (synchronous assumed)
    elif disease_met is not None and str(disease_met).strip().lower() in ("1", "yes", "true"):
        result["ppgl_metastases_v1"] = 4  # Metachronous
    elif mets is not None:
        result["ppgl_metastases_v1"] = 6  # Local, no extension
    else:
        result["ppgl_metastases_v1"] = 7  # Not known

    result["ppgl_metastases_biomaterial_v1"] = None  # No XLSX equivalent

    return result


def map_acc(patient_id, sheets):
    """Map ACC-specific fields."""
    result = {}
    diag = get_first_record(
        sheets.get("ACC_DiagnosticProcedures", pd.DataFrame()), patient_id
    )
    staging = get_first_record(
        sheets.get("ACC_TumorStaging", pd.DataFrame()), patient_id
    )
    surg = get_first_record(
        sheets.get("ACC_Surgery", pd.DataFrame()), patient_id
    )
    fu = get_last_record(
        sheets.get("ACC_FollowUp", pd.DataFrame()), patient_id, "followup_date_1"
    )

    # Hormone secretion (checkbox: 1-10)
    secretion_map = {
        1: "cushings_syndrome",
        # 2 (subclinical) → no direct XLSX field for ACC
        3: "androgens",       # virilisation → androgen excess
        4: "estrogens",       # feminization → estradiol excess
        5: "mineralocorticoids",
        9: None,  # No steroid excess → derive
    }
    for i in range(1, 11):
        result[f"first_surgery_specificities_v1___{i}"] = 0

    if safe_val(diag, "cushings_syndrome") not in (None, 0, "0", "No", "no"):
        result["first_surgery_specificities_v1___1"] = 1
    if safe_val(diag, "glucocorticoids") not in (None, 0, "0", "No", "no"):
        result["first_surgery_specificities_v1___1"] = 1  # May overlap with Cushing
    if safe_val(diag, "androgens") not in (None, 0, "0", "No", "no"):
        result["first_surgery_specificities_v1___3"] = 1
    if safe_val(diag, "estrogens") not in (None, 0, "0", "No", "no"):
        result["first_surgery_specificities_v1___4"] = 1
    if safe_val(diag, "mineralocorticoids") not in (None, 0, "0", "No", "no"):
        result["first_surgery_specificities_v1___5"] = 1
    if safe_val(diag, "precursor_secretion") not in (None, 0, "0", "No", "no"):
        result["first_surgery_specificities_v1___8"] = 1  # Other precursors

    # If no secretion flagged
    hormone = safe_val(diag, "hormonal_hypersecretion")
    if hormone is not None and str(hormone).strip().lower() in ("0", "no", "false"):
        result["first_surgery_specificities_v1___9"] = 1  # No steroid excess

    # ENSAT stage
    ensat = safe_val(staging, "ensat_classification")
    result["acc_ensat_stage_v1"] = ensat  # Assumes XLSX uses same 1-6 coding

    # Resection status
    resection = safe_val(surg, "surgery_overall_resection_status_1")
    result["acc_resection_status_v1"] = resection  # Assumes same coding

    # Adjuvant treatment (checkbox: 1=RT, 2=Mitotane, 3=Chemo, 4=Other, 5=None)
    for i in range(1, 6):
        result[f"acc_adjuvant_treatment_v1___{i}"] = 0

    rt_df = sheets.get("ACC_Radiotherapy", pd.DataFrame())
    mito_df = sheets.get("ACC_Mitotane", pd.DataFrame())
    chemo_df = sheets.get("ACC_Chemotherapy", pd.DataFrame())

    if patient_has_data(rt_df, patient_id):
        result["acc_adjuvant_treatment_v1___1"] = 1
    if patient_has_data(mito_df, patient_id):
        result["acc_adjuvant_treatment_v1___2"] = 1
    if patient_has_data(chemo_df, patient_id):
        result["acc_adjuvant_treatment_v1___3"] = 1
    if all(result[f"acc_adjuvant_treatment_v1___{i}"] == 0 for i in range(1, 5)):
        result["acc_adjuvant_treatment_v1___5"] = 1  # None

    # Recurrence
    relapse = safe_val(fu, "relapse_1")
    if relapse is not None:
        rel_str = str(relapse).strip().lower()
        if rel_str in ("0", "no", "false", "none"):
            result["acc_metastases_v1"] = 1
        elif rel_str in ("1", "yes", "true"):
            result["acc_metastases_v1"] = 3  # Default to metastatic recurrence
        else:
            result["acc_metastases_v1"] = 5  # Unknown
    else:
        result["acc_metastases_v1"] = 5

    result["acc_metastases_biomaterial_v1"] = None  # No XLSX equivalent

    # Advanced treatment (checkbox: 1-8)
    for i in range(1, 9):
        result[f"acc_advanced_treatment_v1___{i}"] = 0
    # Mirror adjuvant treatment detection for advanced context
    if patient_has_data(mito_df, patient_id):
        result["acc_advanced_treatment_v1___2"] = 1
    if patient_has_data(chemo_df, patient_id):
        result["acc_advanced_treatment_v1___3"] = 1

    return result


def map_apa(patient_id, sheets):
    """Map APA-specific fields."""
    result = {}
    hist = get_first_record(
        sheets.get("APA_PatientHistory", pd.DataFrame()), patient_id
    )
    biochem = get_first_record(
        sheets.get("APA_BiochemicalAssessment", pd.DataFrame()), patient_id
    )
    surg_df = sheets.get("APA_Surgery", pd.DataFrame())
    surg = get_first_record(surg_df, patient_id)
    img = get_first_record(
        sheets.get("APA_Imaging", pd.DataFrame()), patient_id
    )

    # Lowest potassium
    k_hist = safe_val(hist, "lowest_kalemia")
    k_biochem = safe_val(biochem, "serum_potassium_1")
    potassium = k_hist if k_hist is not None else k_biochem
    result["apa_potassium_v1"] = potassium

    # Cortisol co-secretion → no direct XLSX field
    result["apa_cortisol_v1"] = None

    # Lateralisation
    # CDE: 1=Unilateral, 2=Bilateral, 3=Uncertain, 4=Unknown
    adrenal_state = safe_val(img, "adrenal_state_1")
    if adrenal_state is not None:
        as_str = str(adrenal_state).strip().lower()
        if "unilateral" in as_str or "uni" in as_str:
            result["apa_lateralization_v1"] = 1
        elif "bilateral" in as_str or "bi" in as_str:
            result["apa_lateralization_v1"] = 2
        else:
            result["apa_lateralization_v1"] = 4
    else:
        result["apa_lateralization_v1"] = 4

    # Lateralisation method (checkbox: 1=AVS, 2=CT only, 3=Nuclear, 4=Other)
    for i in range(1, 5):
        result[f"apa_lateralization_method_v1___{i}"] = 0
    avs = safe_val(biochem, "bilateral_avs_1")
    if avs is not None and str(avs).strip().lower() in ("1", "yes", "true"):
        result["apa_lateralization_method_v1___1"] = 1

    # Diameter
    right = safe_val(surg, "max_tumor_right")
    left = safe_val(surg, "max_tumor_left")
    # Also try imaging
    if right is None:
        right = safe_val(img, "max_tumor_by_ct_right_1")
    if left is None:
        left = safe_val(img, "max_tumor_by_ct_left_1")
    sizes = [s for s in [right, left] if s is not None]
    result["apa_diameter_v1"] = int(max(sizes)) if sizes else None

    # Surgery performed
    has_surg = patient_has_data(surg_df, patient_id)
    result["apa_surgery_v1"] = 1 if has_surg else 0

    # Histotype → no direct XLSX equivalent
    result["apa_histotype_v1"] = None

    # PASO responses → approximate from APA_FollowUp.eval_of_bp_outcomes_1
    fu = get_last_record(
        sheets.get("APA_FollowUp", pd.DataFrame()), patient_id, "followup_date_1"
    )
    result["apa_surgery_biochem_resp_v1"] = None  # No direct mapping
    result["apa_surgery_clinical_resp_v1"] = None  # No direct mapping

    return result


# =============================================================================
# 4. MAIN TRANSLATION PIPELINE
# =============================================================================

def translate_patient(patient_id, sheets):
    """Translate a single patient from XLSX sheets → CDE record dict."""
    ident = sheets.get("Identification", pd.DataFrame())

    # Detect tumour type
    tumour_type = detect_tumour_type(patient_id, sheets)

    # Assemble CDE record
    record = {}

    # Demographics
    record.update(map_identification(patient_id, ident))

    # General clinical
    record.update(map_general_clinical(patient_id, tumour_type, sheets))

    # Biomaterial
    record.update(map_biomaterial(patient_id, tumour_type, sheets))

    # Tumour type
    record["tumor_type_v1"] = tumour_type

    # Tumour-type-specific fields (initialise all to None)
    napaca_fields = [
        "napaca_incidentaloma_v1", "napaca_secretion_v1", "napaca_size_v1",
        "napaca_type_v1", "napaca_other_type_v1",
    ]
    ppgl_fields = [
        "ppgl_syndromic_v1", "ppgl_mutation_name_v1", "ppgl_diameter_v1",
        "ppgl_metastases_v1", "ppgl_metastases_biomaterial_v1",
    ]
    acc_fields = [
        "acc_ensat_stage_v1", "acc_resection_status_v1", "acc_metastases_v1",
        "acc_metastases_biomaterial_v1",
    ]
    apa_fields = [
        "apa_potassium_v1", "apa_cortisol_v1", "apa_lateralization_v1",
        "apa_diameter_v1", "apa_surgery_v1", "apa_histotype_v1",
        "apa_surgery_biochem_resp_v1", "apa_surgery_clinical_resp_v1",
    ]

    for f in napaca_fields + ppgl_fields + acc_fields + apa_fields:
        record.setdefault(f, None)

    # Map tumour-type-specific fields
    if tumour_type == 1:
        record.update(map_napaca(patient_id, sheets))
    elif tumour_type == 2:
        record.update(map_ppgl(patient_id, sheets))
    elif tumour_type == 3:
        record.update(map_acc(patient_id, sheets))
    elif tumour_type == 4:
        record.update(map_apa(patient_id, sheets))

    # Other tumour type
    record["other_tumor_type_v1"] = None

    return record


def main():
    if len(sys.argv) < 3:
        print("Usage: python ensat_xlsx_to_redcap.py <input.xlsx> <output.csv>")
        print()
        print("Translates the old ENSAT registry XLSX export into REDCap CDE format.")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    print(f"Reading XLSX: {input_path}")

    # Read all relevant sheets
    sheet_names = [
        "Identification",
        "ACC_Biomaterial", "ACC_DiagnosticProcedures", "ACC_FollowUp",
        "ACC_Surgery", "ACC_TumorStaging", "ACC_Pathology",
        "ACC_Chemotherapy", "ACC_Mitotane", "ACC_Radiotherapy", "ACC_Radiofrequency",
        "Pheo_PatientHistory", "Pheo_Genetics", "Pheo_TumorDetails",
        "Pheo_BiochemicalAssessment", "Pheo_Surgery", "Pheo_FollowUp",
        "Pheo_Biomaterial",
        "NAPACA_DiagnosticProcedures", "NAPACA_Imaging", "NAPACA_Pathology",
        "NAPACA_Surgery", "NAPACA_FollowUp", "NAPACA_Biomaterial",
        "APA_PatientHistory", "APA_BiochemicalAssessment", "APA_Surgery",
        "APA_FollowUp", "APA_Imaging", "APA_Biomaterial",
    ]

    sheets = {}
    for name in sheet_names:
        print(f"  Reading sheet: {name}...", end=" ")
        sheets[name] = read_sheet(input_path, name)
        n = len(sheets[name])
        print(f"{n} rows")

    # Get all patient IDs from Identification sheet
    ident = sheets["Identification"]
    if ident.empty or "patient_id" not in ident.columns:
        print("ERROR: No patient_id column in Identification sheet.")
        sys.exit(1)

    patient_ids = ident["patient_id"].dropna().unique()
    print(f"\nFound {len(patient_ids)} patients. Translating...")

    # Translate each patient
    records = []
    for i, pid in enumerate(patient_ids):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(patient_ids)}...")
        record = translate_patient(pid, sheets)
        records.append(record)

    # Build output DataFrame
    output_df = pd.DataFrame(records)

    # Replace None/NaN with empty string for REDCap import
    output_df = output_df.fillna("")

    # Write CSV
    output_df.to_csv(output_path, index=False)
    print(f"\nWrote {len(output_df)} records to: {output_path}")
    print(f"Columns: {len(output_df.columns)}")
    print("\nDone.")


if __name__ == "__main__":
    main()
