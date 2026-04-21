from flask import Blueprint, render_template
from app.db import fetch_one, fetch_all

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    summary = fetch_one("""
        SELECT *
        FROM mv_pheno_dashboard_summary
    """)

    organism_overview = fetch_all("""
        SELECT *
        FROM mv_pheno_organism_overview
        ORDER BY n_records DESC, scientific_name
    """)

    organism_effect_type = fetch_all("""
        SELECT         
            organism_id,
            scientific_name,
            common_name,
            uniprot_acronym,
            CASE
                WHEN effect_type = 'GR signaling' THEN 'GR Signaling'
                WHEN effect_type = 'ARE-bla agonism' THEN 'ARE-bla Agonism'
                WHEN effect_type = 'AREc32 agonism' THEN 'AREc32 Agonism'
                WHEN effect_type = 'GR-bla agonism' THEN 'GR-bla Agonism'
                ELSE UPPER(LEFT(effect_type, 1)) || LOWER(SUBSTRING(effect_type FROM 2))
            END AS effect_type,
            n_endpoints
        FROM mv_pheno_organism_effect_type
        ORDER BY scientific_name, effect_type
    """)

    partner_effect_table = fetch_all("""
        SELECT
            partner_id,
            ptox_biosystem_name,
            scientific_name,
            CASE
                WHEN effect_type = 'GR signaling' THEN 'GR Signaling'
                WHEN effect_type = 'ARE-bla agonism' THEN 'ARE-bla Agonism'
                WHEN effect_type = 'AREc32 agonism' THEN 'AREc32 Agonism'
                WHEN effect_type = 'GR-bla agonism' THEN 'GR-bla Agonism'
                ELSE UPPER(LEFT(effect_type, 1)) || LOWER(SUBSTRING(effect_type FROM 2))
            END AS effect_type,
            CASE
                WHEN effect_type_description IS NULL THEN ''
                ELSE effect_type_description
            END AS effect_type_description,
            n_chemicals,
            n_endpoints
        FROM mv_pheno_partner_endpoint_table
        ORDER BY partner_id, ptox_biosystem_name, effect_type
    """)

    return render_template(
        "index.html",
        summary=summary,
        organism_overview=organism_overview,
        organism_effect_type=organism_effect_type,
        partner_effect_table=partner_effect_table,
        control_summary={
            "n_control_conditions": summary["n_control_conditions"],
            "n_treatment_conditions": summary["n_treatment_conditions"],
        },
        aggregated_summary={
            "n_aggregated_experiments": summary["n_aggregated_experiments"],
            "n_non_aggregated_experiments": summary["n_non_aggregated_experiments"],
        },
    )
