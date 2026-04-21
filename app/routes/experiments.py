from flask import Blueprint, render_template, request
from app.db import fetch_all, fetch_one

experiments_bp = Blueprint("experiments", __name__)


@experiments_bp.route("/")
def list_experiments():
    partner_id = request.args.get("partner_id")
    organism = request.args.get("organism")
    batch_id = request.args.get("batch_id")
    aggregated_data = request.args.get("aggregated_data")

    sql = """
        WITH condition_stats AS (
            SELECT
                pcs.phenotype_experiment_id,
                pcs.n_conditions,
                pcs.n_chemicals,
                pcs.n_controls,
                durs.exposure_durations
            FROM (
                SELECT
                    pc.phenotype_experiment_id,
                    COUNT(DISTINCT pc.phenotype_condition_id) AS n_conditions,
                    COUNT(DISTINCT pc.ptx_code) FILTER (WHERE pc.ptx_code IS NOT NULL) AS n_chemicals,
                    COUNT(*) FILTER (WHERE pc.is_control = TRUE) AS n_controls
                FROM phenotype_condition pc
                GROUP BY pc.phenotype_experiment_id
            ) pcs
            LEFT JOIN (
                SELECT
                    dd.phenotype_experiment_id,
                    STRING_AGG(dd.duration_label, ', ' ORDER BY dd.exposure_duration) AS exposure_durations
                FROM (
                    SELECT DISTINCT
                        pc.phenotype_experiment_id,
                        pc.exposure_duration,
                        pc.exposure_duration::TEXT || COALESCE(' ' || pc.exposure_duration_unit, '') AS duration_label
                    FROM phenotype_condition pc
                    WHERE pc.exposure_duration IS NOT NULL
                ) dd
                GROUP BY dd.phenotype_experiment_id
            ) durs
              ON pcs.phenotype_experiment_id = durs.phenotype_experiment_id
        ),
        concentration_counts AS (
            SELECT
                x.phenotype_experiment_id,
                AVG(x.n_concentrations)::NUMERIC(10,2) AS avg_n_concentrations_per_chemical
            FROM (
                SELECT
                    pc.phenotype_experiment_id,
                    pc.ptx_code,
                    COUNT(DISTINCT pc.exposure_concentration) AS n_concentrations
                FROM phenotype_condition pc
                WHERE pc.ptx_code IS NOT NULL
                  AND pc.is_control = FALSE
                GROUP BY pc.phenotype_experiment_id, pc.ptx_code
            ) x
            GROUP BY x.phenotype_experiment_id
        ),
        record_stats AS (
            SELECT
                pc.phenotype_experiment_id,
                COUNT(pr.phenotype_record_id) AS n_records
            FROM phenotype_condition pc
            LEFT JOIN phenotype_record pr
              ON pc.phenotype_condition_id = pr.phenotype_condition_id
            GROUP BY pc.phenotype_experiment_id
        ),
        chemical_lists AS (
            SELECT
                pc.phenotype_experiment_id,
                STRING_AGG(
                    DISTINCT pc.ptx_code::TEXT,
                    '||'
                    ORDER BY pc.ptx_code::TEXT
                ) AS chemical_keys
            FROM phenotype_condition pc
            WHERE pc.ptx_code IS NOT NULL
            AND pc.is_control = FALSE
            GROUP BY pc.phenotype_experiment_id
        ),
        endpoint_counts AS (
            SELECT
                pc.phenotype_experiment_id,
                COUNT(DISTINCT pr.phenotype_effect_id) AS n_endpoints,
                STRING_AGG(
                    DISTINCT pr.phenotype_effect_id::TEXT,
                    '||'
                    ORDER BY pr.phenotype_effect_id::TEXT
                ) AS endpoint_keys
            FROM phenotype_condition pc
            JOIN phenotype_record pr
            ON pc.phenotype_condition_id = pr.phenotype_condition_id
            GROUP BY pc.phenotype_experiment_id
        )
        SELECT
            pe.partner_id,
            pe.internal_experiment_batch_id,
            pe.experiment_date,
            b.ptox_biosystem_name,
            o.scientific_name AS organism,
            pe.medium,
            pe.format_exposure,
            pe.aggregated_data,
            pe.strain,
            pe.quality_flag,
            COALESCE(cs.n_conditions, 0) AS n_conditions,
            COALESCE(cs.n_chemicals, 0) AS n_chemicals,
            COALESCE(cs.n_controls, 0) AS n_controls,
            COALESCE(cc.avg_n_concentrations_per_chemical, 0) AS avg_n_concentrations_per_chemical,
            COALESCE(cs.exposure_durations, '') AS exposure_durations,
            COALESCE(ec.n_endpoints, 0) AS n_endpoints,
            COALESCE(cl.chemical_keys, '') AS chemical_keys,
            COALESCE(ec.endpoint_keys, '') AS endpoint_keys,
            COALESCE(rs.n_records, 0) AS n_records
        FROM phenotype_experiment pe
        JOIN biosystem b
          ON pe.biosystem_id = b.biosystem_id
        JOIN organism o
          ON b.organism_id = o.organism_id
        LEFT JOIN condition_stats cs
          ON pe.phenotype_experiment_id = cs.phenotype_experiment_id
        LEFT JOIN concentration_counts cc
          ON pe.phenotype_experiment_id = cc.phenotype_experiment_id
        LEFT JOIN chemical_lists cl
          ON pe.phenotype_experiment_id = cl.phenotype_experiment_id
        LEFT JOIN endpoint_counts ec
          ON pe.phenotype_experiment_id = ec.phenotype_experiment_id
        LEFT JOIN record_stats rs
          ON pe.phenotype_experiment_id = rs.phenotype_experiment_id
        WHERE
            (:partner_id IS NULL OR pe.partner_id ILIKE :partner_pattern)
            AND (:organism IS NULL OR o.scientific_name ILIKE :organism_pattern)
            AND (:batch_id IS NULL OR pe.internal_experiment_batch_id ILIKE :batch_pattern)
            AND (
                :aggregated_data IS NULL
                OR pe.aggregated_data = CAST(:aggregated_data AS BOOLEAN)
            )
        ORDER BY
            pe.experiment_date DESC NULLS LAST,
            pe.partner_id,
            b.ptox_biosystem_name
    """

    rows = fetch_all(
        sql,
        {
            "partner_id": partner_id or None,
            "partner_pattern": f"%{partner_id}%" if partner_id else None,
            "organism": organism or None,
            "organism_pattern": f"%{organism}%" if organism else None,
            "batch_id": batch_id or None,
            "batch_pattern": f"%{batch_id}%" if batch_id else None,
            "aggregated_data": aggregated_data if aggregated_data in ("true", "false") else None,
        },
    )

    chemical_set = set()
    endpoint_set = set()
    organism_set = set()

    for r in rows:
        organism_set.add(r["organism"])

        for x in (r.get("chemical_keys") or "").split("||"):
            if x:
                chemical_set.add(x)

        for x in (r.get("endpoint_keys") or "").split("||"):
            if x:
                endpoint_set.add(x)

    summary = {
        "n_experiments": len(rows),
        "n_conditions": sum(r["n_conditions"] for r in rows),
        "n_records": sum(r["n_records"] for r in rows),
        "n_chemicals": len(chemical_set),
        "n_organisms": len(organism_set),
        "n_effects": len(endpoint_set),
    }
    # summary = fetch_one("""
    #     SELECT *
    #     FROM mv_pheno_dashboard_summary
    # """)

    col_desc = {
        "#": "Row index",
        "Partner": "Data-contributing partner",
        "Biosystem Code": "PrecisionTox biosystem code (letter)",
        "Organism": "Scientific name of the organism",
        "Strain": "Organism strain or cell line",
        "Strain Generation": "Strain generation information",
        "Date": "Experiment date",
        "Batch ID": "Internal experiment batch identifier",
        "Format": "Type of exposure vessel",
        "Medium": "Exposure medium",
        "Aggregated": "Whether the experiment data are aggregated",
        "Quality": "Quality flag associated with the experiment",
        "# Conditions": "Number of conditions tested in this experiment",
        "# Chemicals": "Number of chemicals tested",
        "# Controls": "Number of control samples in this experiment",
        "Avg. Concentrations / Chemical": "Average number of exposure concentrations per chemical tested in this experiment",
        "Exposure Durations": "List of exposure times tested in this experiment",
        "# Records": "Total number of endpoint measurements in this experiment"        
    }

    return render_template(
        "experiments.html", 
        rows=rows,
        summary=summary,
        columnDes=col_desc
    )
    