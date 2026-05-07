from flask import Blueprint, jsonify, request
from app.db import fetch_all, fetch_one

api_bp = Blueprint("api", __name__)


@api_bp.route("/health")
def health():
    row = fetch_one("SELECT 1 AS ok")
    return jsonify(row)


@api_bp.route("/explore/options")
def explore_options():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)

    categories = []
    endpoints = []
    chemicals = []

    if organism_id is not None:
        categories = fetch_all("""
            SELECT DISTINCT
                pef.type AS effect_type
            FROM phenotype_effect pef
            JOIN biosystem b
              ON pef.biosystem_id = b.biosystem_id
            WHERE b.organism_id = :organism_id
            ORDER BY pef.type
        """, {"organism_id": organism_id})

        endpoints = fetch_all("""
            SELECT DISTINCT
                pef.name AS endpoint_name,
                pef.display_name AS endpoint_display_name
            FROM phenotype_effect pef
            JOIN biosystem b
              ON pef.biosystem_id = b.biosystem_id
            WHERE
                b.organism_id = :organism_id
                AND (:effect_type IS NULL OR pef.type = :effect_type)
            ORDER BY pef.display_name
        """, {"organism_id": organism_id, "effect_type": effect_type or None})

        if endpoint_name:
            chemicals = fetch_all("""
                SELECT DISTINCT
                    c.ptx_code,
                    c.full_ptx_code,
                    c.name
                FROM phenotype_record pr
                JOIN phenotype_condition pc
                  ON pr.phenotype_condition_id = pc.phenotype_condition_id
                JOIN phenotype_experiment pe
                  ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
                JOIN biosystem b
                  ON pe.biosystem_id = b.biosystem_id
                JOIN phenotype_effect pef
                  ON pr.phenotype_effect_id = pef.phenotype_effect_id
                JOIN chemical c
                  ON pc.ptx_code = c.ptx_code
                WHERE
                    b.organism_id = :organism_id
                    AND pr.effect_value IS NOT NULL
                    AND pc.is_control = FALSE
                    AND pef.name = :endpoint_name
                ORDER BY c.ptx_code
            """, {
                "organism_id": organism_id,
                "endpoint_name": endpoint_name,
            })
        else:
            chemicals = fetch_all("""
                SELECT DISTINCT
                    c.ptx_code,
                    c.full_ptx_code,
                    c.name
                FROM phenotype_condition pc
                JOIN phenotype_experiment pe
                  ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
                JOIN biosystem b
                  ON pe.biosystem_id = b.biosystem_id
                JOIN chemical c
                  ON pc.ptx_code = c.ptx_code
                WHERE
                    b.organism_id = :organism_id
                    AND pc.is_control = FALSE
                ORDER BY c.name
            """, {"organism_id": organism_id})

    return jsonify({
        "categories": categories,
        "endpoints": endpoints,
        "chemicals": chemicals,
    })


@api_bp.route("/explore/info")
def explore_info():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)

    organism_info = None
    category_info = None
    endpoint_info = None

    if organism_id:
        organism_rows = fetch_all("""
            SELECT DISTINCT
                o.scientific_name,
                o.uniprot_acronym,
                o.ncbi_tax_id,
                b.ptox_biosystem_code
            FROM phenotype_experiment pe
            JOIN biosystem b
              ON pe.biosystem_id = b.biosystem_id
            JOIN organism o
              ON b.organism_id = o.organism_id
            WHERE o.organism_id = :organism_id
            ORDER BY b.ptox_biosystem_code
        """, {"organism_id": organism_id})

        if organism_rows:
            biosystem_codes = sorted({
                r["ptox_biosystem_code"] for r in organism_rows if r["ptox_biosystem_code"]
            })
            first = organism_rows[0]
            organism_info = {
                "scientific_name": first["scientific_name"],
                "uniprot_acronym": first["uniprot_acronym"],
                "ncbi_tax_id": first["ncbi_tax_id"],
                "biosystem_code": ", ".join(biosystem_codes),
            }

    if organism_id and effect_type:
        category_row = fetch_all("""
            SELECT
                pef.type AS effect_type,
                pef.type_description,
                COUNT(DISTINCT pef.name) AS n_endpoints
            FROM phenotype_effect pef
            JOIN biosystem b
              ON pef.biosystem_id = b.biosystem_id
            WHERE
                b.organism_id = :organism_id
                AND pef.type = :effect_type
            GROUP BY
                pef.type,
                pef.type_description
        """, {
            "organism_id": organism_id,
            "effect_type": effect_type,
        })

        if category_row:
            category_info = category_row[0]

    if organism_id and effect_type and endpoint_name:
        endpoint_row = fetch_all("""
            SELECT
                pef.display_name,
                pef.name,
                pef.ontology_term,
                pef.description,
                pef.unit,
                pef.data_type
            FROM phenotype_effect pef
            JOIN biosystem b
              ON pef.biosystem_id = b.biosystem_id
            WHERE
                b.organism_id = :organism_id
                AND pef.type = :effect_type
                AND pef.name = :endpoint_name
            LIMIT 1
        """, {
            "organism_id": organism_id,
            "effect_type": effect_type,
            "endpoint_name": endpoint_name,
        })

        if endpoint_row:
            endpoint_info = endpoint_row[0]

    return jsonify({
        "organism": organism_info,
        "category": category_info,
        "endpoint": endpoint_info,
    })


@api_bp.route("/explore/histogram")
def explore_histogram():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)

    if not organism_id or not effect_type or not endpoint_name:
        return jsonify({
            "control_values": [],
            "exposure_values": [],
            "endpoint_unit": None,
            "endpoint_label": None,
        })

    rows = fetch_all("""
        SELECT
            pc.is_control,
            CAST(pr.effect_value AS DOUBLE PRECISION) AS value_num,
            pef.unit AS endpoint_unit,
            pef.display_name AS endpoint_label
        FROM phenotype_record pr
        JOIN phenotype_condition pc
          ON pr.phenotype_condition_id = pc.phenotype_condition_id
        JOIN phenotype_experiment pe
          ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
        JOIN biosystem b
          ON pe.biosystem_id = b.biosystem_id
        JOIN phenotype_effect pef
          ON pr.phenotype_effect_id = pef.phenotype_effect_id
        WHERE
            b.organism_id = :organism_id
            AND pef.type = :effect_type
            AND pef.name = :endpoint_name
            AND pr.effect_value IS NOT NULL
            AND pr.effect_value ~ '^[+-]?([0-9]*[.])?[0-9]+$'
    """, {
        "organism_id": organism_id,
        "effect_type": effect_type,
        "endpoint_name": endpoint_name,
    })

    control_values = [float(r["value_num"]) for r in rows if r["is_control"]]
    exposure_values = [float(r["value_num"]) for r in rows if not r["is_control"]]

    control_mean = sum(control_values) / len(control_values) if control_values else None
    exposure_mean = sum(exposure_values) / len(exposure_values) if exposure_values else None

    endpoint_row = fetch_all("""
        SELECT pef.display_name, pef.unit
        FROM phenotype_effect pef
        JOIN biosystem b
          ON pef.biosystem_id = b.biosystem_id
        WHERE
            b.organism_id = :organism_id
            AND pef.type = :effect_type
            AND pef.name = :endpoint_name
        LIMIT 1
    """, {
        "organism_id": organism_id,
        "effect_type": effect_type,
        "endpoint_name": endpoint_name,
    })

    endpoint_label = endpoint_row[0]["display_name"] if endpoint_row else endpoint_name
    endpoint_unit = endpoint_row[0]["unit"] if endpoint_row else None

    return jsonify({
        "control_values": control_values,
        "exposure_values": exposure_values,
        "control_mean": control_mean,
        "exposure_mean": exposure_mean,
        "n_control": len(control_values),
        "n_exposure": len(exposure_values),
        "endpoint_label": endpoint_label,
        "endpoint_unit": endpoint_unit,
    })


@api_bp.route("/explore/dose_response")
def explore_dose_response():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)
    ptx_code = request.args.get("ptx_code", type=int)

    if not organism_id or not effect_type or not endpoint_name or not ptx_code:
        return jsonify({
            "series": [],
            "x_unit": None,
            "y_unit": None,
            "endpoint_label": None,
        })

    rows = fetch_all("""
        WITH numeric_records AS (
            SELECT
                pe.phenotype_experiment_id,
                pe.experiment_date,
                pe.internal_experiment_batch_id AS batch_id,
                pc.phenotype_condition_id,
                pc.is_control,
                pc.exposure_concentration,
                pc.exposure_concentration_unit,
                pc.exposure_duration,
                pc.exposure_duration_unit,
                pef.display_name AS endpoint_label,
                pef.unit AS endpoint_unit,
                CAST(pr.effect_value AS DOUBLE PRECISION) AS value_num
            FROM phenotype_record pr
            JOIN phenotype_condition pc
              ON pr.phenotype_condition_id = pc.phenotype_condition_id
            JOIN phenotype_experiment pe
              ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
            JOIN biosystem b
              ON pe.biosystem_id = b.biosystem_id
            JOIN phenotype_effect pef
              ON pr.phenotype_effect_id = pef.phenotype_effect_id
            WHERE
                b.organism_id = :organism_id
                AND pef.type = :effect_type
                AND pef.name = :endpoint_name
                AND pr.effect_value IS NOT NULL
                AND pr.effect_value ~ '^[+-]?([0-9]*[.])?[0-9]+$'
                AND (
                    pc.is_control = TRUE
                    OR (pc.is_control = FALSE AND pc.ptx_code = :ptx_code)
                )
        ),
        condition_means AS (
            SELECT
                phenotype_experiment_id,
                experiment_date,
                batch_id,
                phenotype_condition_id,
                is_control,
                exposure_concentration,
                exposure_concentration_unit,
                exposure_duration,
                exposure_duration_unit,
                endpoint_label,
                endpoint_unit,
                AVG(value_num) AS condition_mean
            FROM numeric_records
            GROUP BY
                phenotype_experiment_id,
                batch_id,
                experiment_date,
                phenotype_condition_id,
                is_control,
                exposure_concentration,
                exposure_concentration_unit,
                exposure_duration,
                exposure_duration_unit,
                endpoint_label,
                endpoint_unit
        ),
        control_summary AS (
            SELECT
                phenotype_experiment_id,
                batch_id,
                AVG(condition_mean) AS control_mean
            FROM condition_means
            WHERE is_control = TRUE
            GROUP BY phenotype_experiment_id, batch_id
        ),
        exposure_summary AS (
            SELECT
                cm.phenotype_experiment_id,
                cm.experiment_date,
                cm.batch_id,
                cm.exposure_concentration,
                cm.exposure_concentration_unit,
                cm.exposure_duration,
                cm.exposure_duration_unit,
                cm.endpoint_label,
                cm.endpoint_unit,
                AVG(cm.condition_mean) AS mean_value,
                CASE
                    WHEN COUNT(*) > 1
                    THEN STDDEV_SAMP(cm.condition_mean) / SQRT(COUNT(*))
                    ELSE NULL
                END AS sem_value,
                COUNT(*) AS n_conditions
            FROM condition_means cm
            WHERE cm.is_control = FALSE
            GROUP BY
                cm.phenotype_experiment_id,
                cm.experiment_date,
                cm.batch_id,
                cm.exposure_concentration,
                cm.exposure_concentration_unit,
                cm.exposure_duration,
                cm.exposure_duration_unit,
                cm.endpoint_label,
                cm.endpoint_unit
        )
        SELECT
            es.phenotype_experiment_id,
            es.experiment_date,
            es.batch_id,
            es.exposure_concentration,
            es.exposure_concentration_unit,
            es.exposure_duration,
            es.exposure_duration_unit,
            es.endpoint_label,
            es.endpoint_unit,
            es.mean_value,
            es.sem_value,
            es.n_conditions,
            cs.control_mean
        FROM exposure_summary es
        LEFT JOIN control_summary cs
          ON es.phenotype_experiment_id = cs.phenotype_experiment_id
         AND es.batch_id IS NOT DISTINCT FROM cs.batch_id
        ORDER BY
            es.batch_id,
            es.exposure_duration NULLS FIRST,
            es.exposure_concentration
    """, {
        "organism_id": organism_id,
        "effect_type": effect_type,
        "endpoint_name": endpoint_name,
        "ptx_code": ptx_code,
    })

    series_map = {}
    x_units = set()
    y_units = set()
    endpoint_labels = set()

    for r in rows:
        if r["exposure_concentration_unit"]:
            x_units.add(r["exposure_concentration_unit"])
        if r["endpoint_unit"]:
            y_units.add(r["endpoint_unit"])
        if r["endpoint_label"]:
            endpoint_labels.add(r["endpoint_label"])

        duration_label = ""
        if r["exposure_duration"] is not None:
            duration_label = f'{r["exposure_duration"]} {r["exposure_duration_unit"] or ""}'.strip()

        series_key = (
            r["phenotype_experiment_id"],
            r["batch_id"],
            r["experiment_date"],
            duration_label,
        )

        series = series_map.setdefault(series_key, {
            "label": "",
            "exp_id": r["phenotype_experiment_id"],
            "batch_id": r["batch_id"],
            "experiment_date": r["experiment_date"],
            "duration_label": duration_label,
            "x": [],
            "y": [],
            "sem": [],
            "n_conditions": [],
            "control_mean": None if r["control_mean"] is None else float(r["control_mean"]),
        })

        series["x"].append(float(r["exposure_concentration"]))
        series["y"].append(float(r["mean_value"]))
        series["sem"].append(None if r["sem_value"] is None else float(r["sem_value"]))
        series["n_conditions"].append(int(r["n_conditions"]))

    x_unit = next(iter(x_units)) if len(x_units) == 1 else None
    y_unit = next(iter(y_units)) if len(y_units) == 1 else None
    endpoint_label = next(iter(endpoint_labels)) if len(endpoint_labels) == 1 else endpoint_name

    return jsonify({
        "series": sorted(
            series_map.values(),
            key=lambda s: (
                s["duration_label"] or "",
                s["batch_id"] or "",
                s["experiment_date"] or "",
                s["exp_id"] or 0,
            )
        ),
        "x_unit": x_unit,
        "y_unit": y_unit,
        "endpoint_label": endpoint_label,
    })

@api_bp.route("/explore/ranking")
def explore_ranking():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)

    if not organism_id or not effect_type or not endpoint_name:
        return jsonify({"rows": [], "endpoint_label": None, "endpoint_unit": None})

    rows = fetch_all("""
        WITH numeric_records AS (
            SELECT
                c.ptx_code,
                c.full_ptx_code,
                c.name AS chemical_name,
                pef.display_name AS endpoint_label,
                pef.unit AS endpoint_unit,
                pc.is_control,
                pc.exposure_concentration,
                CAST(pr.effect_value AS DOUBLE PRECISION) AS value_num
            FROM phenotype_record pr
            JOIN phenotype_condition pc
              ON pr.phenotype_condition_id = pc.phenotype_condition_id
            JOIN phenotype_experiment pe
              ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
            JOIN biosystem b
              ON pe.biosystem_id = b.biosystem_id
            JOIN phenotype_effect pef
              ON pr.phenotype_effect_id = pef.phenotype_effect_id
            LEFT JOIN chemical c
              ON pc.ptx_code = c.ptx_code
            WHERE
                b.organism_id = :organism_id
                AND pef.type = :effect_type
                AND pef.name = :endpoint_name
                AND pr.effect_value IS NOT NULL
                AND pr.effect_value ~ '^[+-]?([0-9]*[.])?[0-9]+$'
        ),
        max_conc_per_chemical AS (
            SELECT
                ptx_code,
                MAX(exposure_concentration) AS max_conc
            FROM numeric_records
            WHERE is_control = FALSE
              AND ptx_code IS NOT NULL
            GROUP BY ptx_code
        ),
        endpoint_at_max AS (
            SELECT
                nr.full_ptx_code,
                nr.chemical_name,
                nr.endpoint_label,
                nr.endpoint_unit,
                AVG(nr.value_num) AS mean_value
            FROM numeric_records nr
            JOIN max_conc_per_chemical mc
              ON nr.ptx_code = mc.ptx_code
             AND nr.exposure_concentration = mc.max_conc
            WHERE nr.is_control = FALSE
            GROUP BY
                nr.full_ptx_code,
                nr.chemical_name,
                nr.endpoint_label,
                nr.endpoint_unit
        )
        SELECT
            full_ptx_code,
            chemical_name,
            endpoint_label,
            endpoint_unit,
            mean_value
        FROM endpoint_at_max
        ORDER BY mean_value DESC, chemical_name
    """, {
        "organism_id": organism_id,
        "effect_type": effect_type,
        "endpoint_name": endpoint_name,
    })

    endpoint_label = rows[0]["endpoint_label"] if rows else endpoint_name
    endpoint_unit = rows[0]["endpoint_unit"] if rows else None

    return jsonify({
        "rows": rows,
        "endpoint_label": endpoint_label,
        "endpoint_unit": endpoint_unit,
    })

@api_bp.route("/explore/table")
def explore_table():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)
    ptx_code = request.args.get("ptx_code", type=int)
    show_all = request.args.get("show_all", "0") == "1"

    if not organism_id:
        return jsonify({"rows": []})

    sql = """
        SELECT
            pr.phenotype_record_id,
            pc.phenotype_condition_id,
            pe.phenotype_experiment_id,
            pe.partner_id,
            pe.internal_experiment_batch_id,
            pe.experiment_date,
            b.ptox_biosystem_code AS biosystem_code,
            o.scientific_name AS organism,
            pe.strain,
            pe.strain_generation,
            o.uniprot_acronym,
            c.full_ptx_code,
            c.name AS chemical_name,
            pc.sample_type,
            pc.is_control,
            pc.exposure_concentration,
            pc.exposure_concentration_unit,
            pc.exposure_duration,
            pc.exposure_duration_unit,
            pc.stage_organism_exposure_start AS stage_exp,
            pc.stage_organism_observation_start AS stage_obs,
            pc.stage_organism_unit AS stage_unit,
            pc.well_name_vessel_name AS well_name,
            pc.container_id,
            pe.exposure_temperature,
            pef.type AS endpoint_category,
            pef.name AS endpoint_name,
            pef.display_name AS endpoint_display_name,
            pef.unit AS endpoint_unit,
            pr.effect_value,
            pr.effect_value_scaling_factor,
            pe.medium,
            pe.solvent,
            pe.solvent_proportion,
            pe.buffer,
            pe.buffer_concentration,
            pe.buffer_concentration_unit,
            pe.format_exposure,
            pe.test_volume_per_well_ml AS test_vol,
            pe.number_organisms_cells AS num_org,
            pe.aggregated_data,
            pe.quality_flag
        FROM phenotype_record pr
        JOIN phenotype_condition pc
          ON pr.phenotype_condition_id = pc.phenotype_condition_id
        JOIN phenotype_experiment pe
          ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
        JOIN biosystem b
          ON pe.biosystem_id = b.biosystem_id
        JOIN organism o
          ON b.organism_id = o.organism_id
        JOIN phenotype_effect pef
          ON pr.phenotype_effect_id = pef.phenotype_effect_id
        LEFT JOIN chemical c
          ON pc.ptx_code = c.ptx_code
        WHERE
            b.organism_id = :organism_id
            AND (:effect_type IS NULL OR pef.type = :effect_type)
            AND (:endpoint_name IS NULL OR pef.name = :endpoint_name)
            AND (
                :ptx_code IS NULL
                OR (pc.is_control = FALSE AND pc.ptx_code = :ptx_code)
                OR pc.is_control = TRUE
            )
        ORDER BY
            c.name NULLS FIRST,
            pe.internal_experiment_batch_id NULLS LAST,
            pc.exposure_duration NULLS FIRST,
            pc.exposure_concentration NULLS FIRST,
            pr.phenotype_record_id
    """

    if not show_all:
        sql += "\n LIMIT 5000"

    rows = fetch_all(sql, {
        "organism_id": organism_id,
        "effect_type": effect_type or None,
        "endpoint_name": endpoint_name or None,
        "ptx_code": ptx_code,
    })

    return jsonify({
        "rows": rows,
        "is_truncated": (not show_all and len(rows) == 5000),
        "show_all": show_all,
    })

@api_bp.route("/compare/options")
def compare_options():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)

    if not organism_id:
        return jsonify({"categories": [], "endpoints": []})

    categories = fetch_all("""
        SELECT DISTINCT
            pef.type AS effect_type
        FROM phenotype_effect pef
        JOIN biosystem b
          ON pef.biosystem_id = b.biosystem_id
        WHERE b.organism_id = :organism_id
        ORDER BY pef.type
    """, {"organism_id": organism_id})

    endpoints = fetch_all("""
        SELECT DISTINCT
            pef.name AS endpoint_name,
            pef.display_name AS endpoint_display_name
        FROM phenotype_effect pef
        JOIN biosystem b
          ON pef.biosystem_id = b.biosystem_id
        WHERE
            b.organism_id = :organism_id
            AND (:effect_type IS NULL OR pef.type = :effect_type)
        ORDER BY pef.display_name
    """, {
        "organism_id": organism_id,
        "effect_type": effect_type or None,
    })

    return jsonify({"categories": categories, "endpoints": endpoints})

@api_bp.route("/compare/heatmap")
def compare_heatmap():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)
    metric = request.args.get("metric", default="difference", type=str)

    if not organism_id:
        return jsonify({
            "x": [],
            "y": [],
            "z": [],
            "customdata": [],
            "metric": metric,
        })

    if metric == "zscore":
        metric_expr = """
            CASE
                WHEN cs.control_mean IS NOT NULL
                 AND cs.control_sd IS NOT NULL
                 AND cs.control_sd <> 0
                    THEN (ts.treatment_mean - cs.control_mean) / cs.control_sd
                ELSE NULL
            END
        """
    else:
        metric = "difference"
        metric_expr = """
            CASE
                WHEN cs.control_mean IS NOT NULL
                    THEN ts.treatment_mean - cs.control_mean
                ELSE ts.treatment_mean
            END
        """

    sql = f"""
        WITH numeric_records AS (
            SELECT
                c.ptx_code,
                c.full_ptx_code,
                c.name AS chemical_name,
                pe.phenotype_experiment_id,
                pc.phenotype_condition_id,
                pc.is_control,
                pef.phenotype_effect_id,
                pef.type AS effect_type,
                pef.display_name AS endpoint_label,
                pef.unit AS endpoint_unit,
                CAST(pr.effect_value AS DOUBLE PRECISION) AS value_num
            FROM phenotype_record pr
            JOIN phenotype_condition pc
              ON pr.phenotype_condition_id = pc.phenotype_condition_id
            JOIN phenotype_experiment pe
              ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
            JOIN biosystem b
              ON pe.biosystem_id = b.biosystem_id
            JOIN phenotype_effect pef
              ON pr.phenotype_effect_id = pef.phenotype_effect_id
            LEFT JOIN chemical c
              ON pc.ptx_code = c.ptx_code
            WHERE
                b.organism_id = :organism_id
                AND (:effect_type IS NULL OR pef.type = :effect_type)
                AND (:endpoint_name IS NULL OR pef.name = :endpoint_name)
                AND pr.effect_value IS NOT NULL
                AND pr.effect_value ~ '^[+-]?([0-9]*[.])?[0-9]+$'
        ),
        condition_means AS (
            SELECT
                ptx_code,
                full_ptx_code,
                chemical_name,
                phenotype_experiment_id,
                phenotype_condition_id,
                is_control,
                phenotype_effect_id,
                effect_type,
                endpoint_label,
                endpoint_unit,
                AVG(value_num) AS condition_mean
            FROM numeric_records
            GROUP BY
                ptx_code,
                full_ptx_code,
                chemical_name,
                phenotype_experiment_id,
                phenotype_condition_id,
                is_control,
                phenotype_effect_id,
                effect_type,
                endpoint_label,
                endpoint_unit
        ),
        control_stats AS (
            SELECT
                phenotype_experiment_id,
                phenotype_effect_id,
                AVG(condition_mean) AS control_mean,
                STDDEV_SAMP(condition_mean) AS control_sd
            FROM condition_means
            WHERE is_control = TRUE
            GROUP BY phenotype_experiment_id, phenotype_effect_id
        ),
        treatment_stats AS (
            SELECT
                ptx_code,
                full_ptx_code,
                chemical_name,
                phenotype_experiment_id,
                phenotype_effect_id,
                effect_type,
                endpoint_label,
                endpoint_unit,
                AVG(condition_mean) AS treatment_mean
            FROM condition_means
            WHERE is_control = FALSE
              AND ptx_code IS NOT NULL
            GROUP BY
                ptx_code,
                full_ptx_code,
                chemical_name,
                phenotype_experiment_id,
                phenotype_effect_id,
                effect_type,
                endpoint_label,
                endpoint_unit
        ),
        experiment_level_values AS (
            SELECT
                ts.ptx_code,
                ts.full_ptx_code,
                ts.chemical_name,
                ts.phenotype_effect_id,
                ts.effect_type,
                ts.endpoint_label,
                ts.endpoint_unit,
                {metric_expr} AS plot_value,
                CASE WHEN cs.control_mean IS NOT NULL THEN TRUE ELSE FALSE END AS has_control
            FROM treatment_stats ts
            LEFT JOIN control_stats cs
              ON ts.phenotype_experiment_id = cs.phenotype_experiment_id
             AND ts.phenotype_effect_id = cs.phenotype_effect_id
        )
        SELECT
            CONCAT('[', ev.full_ptx_code, '] ', ev.chemical_name) AS chemical_label,
            CONCAT('[', ev.effect_type, '] ', ev.endpoint_label) AS endpoint_label,
            AVG(ev.plot_value) AS mean_value,
            COUNT(*) AS n_experiments,
            COUNT(*) FILTER (WHERE ev.has_control) AS n_with_control,
            COUNT(*) FILTER (WHERE NOT ev.has_control) AS n_without_control
        FROM experiment_level_values ev
        WHERE ev.plot_value IS NOT NULL
        GROUP BY
            ev.full_ptx_code,
            ev.chemical_name,
            ev.effect_type,
            ev.endpoint_label
        ORDER BY
            ev.full_ptx_code,
            ev.chemical_name,
            ev.effect_type,
            ev.endpoint_label
    """

    rows = fetch_all(sql, {
        "organism_id": organism_id,
        "effect_type": effect_type or None,
        "endpoint_name": endpoint_name or None,
    })

    chemical_rows = fetch_all("""
        SELECT DISTINCT
            c.full_ptx_code,
            c.name
        FROM phenotype_condition pc
        JOIN phenotype_experiment pe
        ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
        JOIN biosystem b
        ON pe.biosystem_id = b.biosystem_id
        JOIN chemical c
        ON pc.ptx_code = c.ptx_code
        WHERE
            b.organism_id = :organism_id
            AND pc.is_control = FALSE
        ORDER BY c.full_ptx_code, c.name
    """, {"organism_id": organism_id})

    if not rows:
        return jsonify({
            "x": [],
            "y": [],
            "z": [],
            "customdata": [],
            "metric": metric,
        })

    chemicals = [f'[{r["full_ptx_code"]}] {r["name"]}' for r in chemical_rows]
    endpoints = sorted({r["endpoint_label"] for r in rows})

    value_map = {(r["chemical_label"], r["endpoint_label"]): float(r["mean_value"]) for r in rows}
    n_exp_map = {(r["chemical_label"], r["endpoint_label"]): int(r["n_experiments"]) for r in rows}
    n_ctrl_map = {(r["chemical_label"], r["endpoint_label"]): int(r["n_with_control"]) for r in rows}
    n_noctrl_map = {(r["chemical_label"], r["endpoint_label"]): int(r["n_without_control"]) for r in rows}

    z = []
    customdata = []
    for chem in chemicals:
        z_row = []
        c_row = []
        for endpoint in endpoints:
            key = (chem, endpoint)
            z_row.append(value_map.get(key, None))
            c_row.append([
                n_exp_map.get(key, 0),
                n_ctrl_map.get(key, 0),
                n_noctrl_map.get(key, 0),
            ])
        z.append(z_row)
        customdata.append(c_row)

    import math

    col_means = []
    for j in range(len(endpoints)):
        vals = [z[i][j] for i in range(len(chemicals)) if z[i][j] is not None]
        col_means.append(sum(vals) / len(vals) if vals else 0.0)

    filled = []
    for i in range(len(chemicals)):
        filled.append([
            z[i][j] if z[i][j] is not None else col_means[j]
            for j in range(len(endpoints))
        ])

    remaining = list(range(len(chemicals)))
    order = []

    row_means = [sum(row) / len(row) if row else 0 for row in filled]
    start = min(remaining, key=lambda i: row_means[i]) if remaining else None
    if start is not None:
        order.append(start)
        remaining.remove(start)

    def dist(a, b):
        return math.sqrt(sum((filled[a][k] - filled[b][k]) ** 2 for k in range(len(endpoints))))

    while remaining:
        last = order[-1]
        nxt = min(remaining, key=lambda i: dist(last, i))
        order.append(nxt)
        remaining.remove(nxt)

    chemicals_ordered = [chemicals[i] for i in order]
    z_ordered = [z[i] for i in order]
    custom_ordered = [customdata[i] for i in order]

    return jsonify({
        "x": endpoints,
        "y": chemicals_ordered,
        "z": z_ordered,
        "customdata": custom_ordered,
        "metric": metric,
    })

@api_bp.route("/compare/table")
def compare_table():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)
    show_all = request.args.get("show_all", "0") == "1"

    if not organism_id:
        return jsonify({"rows": [], "is_truncated": False, "show_all": show_all})

    sql = """
        SELECT
            pr.phenotype_record_id,
            pe.partner_id,
            pe.internal_experiment_batch_id,
            pe.experiment_date,
            b.ptox_biosystem_code AS biosystem_code,
            o.scientific_name AS organism,
            c.full_ptx_code,
            c.name AS chemical_name,
            pc.is_control,
            pc.exposure_concentration,
            pc.exposure_concentration_unit,
            pc.exposure_duration,
            pc.exposure_duration_unit,
            pef.type AS endpoint_category,
            pef.name AS endpoint_name,
            pef.display_name AS endpoint_display_name,
            pef.unit AS endpoint_unit,
            pr.effect_value,
            pe.medium,
            pe.format_exposure,
            pe.aggregated_data,
            pe.quality_flag
        FROM phenotype_record pr
        JOIN phenotype_condition pc
          ON pr.phenotype_condition_id = pc.phenotype_condition_id
        JOIN phenotype_experiment pe
          ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
        JOIN biosystem b
          ON pe.biosystem_id = b.biosystem_id
        JOIN organism o
          ON b.organism_id = o.organism_id
        JOIN phenotype_effect pef
          ON pr.phenotype_effect_id = pef.phenotype_effect_id
        LEFT JOIN chemical c
          ON pc.ptx_code = c.ptx_code
        WHERE
            b.organism_id = :organism_id
            AND (:effect_type IS NULL OR pef.type = :effect_type)
            AND (:endpoint_name IS NULL OR pef.name = :endpoint_name)
        ORDER BY
            c.name NULLS FIRST,
            pe.internal_experiment_batch_id NULLS LAST,
            pc.exposure_duration NULLS FIRST,
            pc.exposure_concentration NULLS FIRST,
            pr.phenotype_record_id
    """
    if not show_all:
        sql += "\n LIMIT 5000"

    rows = fetch_all(sql, {
        "organism_id": organism_id,
        "effect_type": effect_type or None,
        "endpoint_name": endpoint_name or None,
    })

    return jsonify({
        "rows": rows,
        "is_truncated": (not show_all and len(rows) == 5000),
        "show_all": show_all,
    })


# @api_bp.route("/heatmap")
# def heatmap_data():
#     organism_id = request.args.get("organism_id", type=int)
#     effect_type = request.args.get("effect_type", type=str)
#     top_n_chemicals = request.args.get("top_n_chemicals", default=20, type=int)
#     top_n_effects = request.args.get("top_n_effects", default=20, type=int)

#     sql = """
#         WITH numeric_records AS (
#             SELECT
#                 o.organism_id,
#                 o.uniprot_acronym,
#                 pe.phenotype_experiment_id,
#                 pc.phenotype_condition_id,
#                 pc.is_control,
#                 c.full_ptx_code,
#                 c.name AS chemical_name,
#                 pef.phenotype_effect_id,
#                 pef.display_name AS effect_name,
#                 pef.type AS effect_type,
#                 CAST(pr.effect_value AS DOUBLE PRECISION) AS effect_value_num
#             FROM phenotype_record pr
#             JOIN phenotype_condition pc
#                 ON pr.phenotype_condition_id = pc.phenotype_condition_id
#             JOIN phenotype_experiment pe
#                 ON pc.phenotype_experiment_id = pe.phenotype_experiment_id
#             JOIN biosystem b
#                 ON pe.biosystem_id = b.biosystem_id
#             JOIN organism o
#                 ON b.organism_id = o.organism_id
#             JOIN phenotype_effect pef
#                 ON pr.phenotype_effect_id = pef.phenotype_effect_id
#             LEFT JOIN chemical c
#                 ON pc.ptx_code = c.ptx_code
#             WHERE
#                 pr.effect_value IS NOT NULL
#                 AND pr.effect_value ~ '^[+-]?([0-9]*[.])?[0-9]+$'
#                 AND (:organism_id IS NULL OR o.organism_id = :organism_id)
#                 AND (:effect_type IS NULL OR pef.type = :effect_type)
#         ),
#         condition_endpoint_means AS (
#             SELECT
#                 organism_id,
#                 uniprot_acronym,
#                 phenotype_experiment_id,
#                 phenotype_condition_id,
#                 is_control,
#                 full_ptx_code,
#                 chemical_name,
#                 phenotype_effect_id,
#                 effect_name,
#                 effect_type,
#                 AVG(effect_value_num) AS condition_mean
#             FROM numeric_records
#             GROUP BY
#                 organism_id,
#                 uniprot_acronym,
#                 phenotype_experiment_id,
#                 phenotype_condition_id,
#                 is_control,
#                 full_ptx_code,
#                 chemical_name,
#                 phenotype_effect_id,
#                 effect_name,
#                 effect_type
#         ),
#         control_endpoint_means AS (
#             SELECT
#                 organism_id,
#                 uniprot_acronym,
#                 phenotype_experiment_id,
#                 phenotype_effect_id,
#                 effect_name,
#                 effect_type,
#                 AVG(condition_mean) AS control_mean
#             FROM condition_endpoint_means
#             WHERE is_control = TRUE
#             GROUP BY
#                 organism_id,
#                 uniprot_acronym,
#                 phenotype_experiment_id,
#                 phenotype_effect_id,
#                 effect_name,
#                 effect_type
#         ),
#         treatment_condition_values AS (
#             SELECT
#                 t.organism_id,
#                 t.uniprot_acronym,
#                 t.full_ptx_code,
#                 t.chemical_name,
#                 t.effect_name,
#                 t.effect_type,
#                 t.phenotype_experiment_id,
#                 t.phenotype_condition_id,
#                 CASE
#                     WHEN c.control_mean IS NOT NULL
#                         THEN t.condition_mean - c.control_mean
#                     ELSE t.condition_mean
#                 END AS plot_value,
#                 CASE
#                     WHEN c.control_mean IS NOT NULL THEN TRUE
#                     ELSE FALSE
#                 END AS has_control
#             FROM condition_endpoint_means t
#             LEFT JOIN control_endpoint_means c
#                 ON t.organism_id = c.organism_id
#                AND t.phenotype_experiment_id = c.phenotype_experiment_id
#                AND t.phenotype_effect_id = c.phenotype_effect_id
#             WHERE
#                 t.is_control = FALSE
#                 AND t.chemical_name IS NOT NULL
#         ),
#         top_chemicals AS (
#             SELECT
#                 full_ptx_code,
#                 chemical_name
#             FROM treatment_condition_values
#             GROUP BY full_ptx_code, chemical_name
#             ORDER BY COUNT(*) DESC, chemical_name
#             LIMIT :top_n_chemicals
#         ),
#         top_endpoints AS (
#             SELECT
#                 uniprot_acronym,
#                 effect_type,
#                 effect_name
#             FROM treatment_condition_values
#             GROUP BY uniprot_acronym, effect_type, effect_name
#             ORDER BY COUNT(*) DESC, effect_name
#             LIMIT :top_n_effects
#         )
#         SELECT
#             CONCAT('[', tcv.full_ptx_code, '] ', tcv.chemical_name) AS chemical_label,
#             CONCAT(
#                 '[',
#                 COALESCE(tcv.uniprot_acronym, 'NA'),
#                 '] ',
#                 '[',
#                 tcv.effect_type,
#                 '] ',
#                 tcv.effect_name
#             ) AS endpoint_label,
#             AVG(tcv.plot_value) AS mean_value,
#             COUNT(*) AS n_conditions,
#             COUNT(*) FILTER (WHERE tcv.has_control) AS n_with_control,
#             COUNT(*) FILTER (WHERE NOT tcv.has_control) AS n_without_control
#         FROM treatment_condition_values tcv
#         JOIN top_chemicals tc
#             ON tcv.full_ptx_code = tc.full_ptx_code
#            AND tcv.chemical_name = tc.chemical_name
#         JOIN top_endpoints te
#             ON tcv.uniprot_acronym IS NOT DISTINCT FROM te.uniprot_acronym
#            AND tcv.effect_type = te.effect_type
#            AND tcv.effect_name = te.effect_name
#         GROUP BY
#             chemical_label,
#             endpoint_label
#         ORDER BY
#             chemical_label,
#             endpoint_label
#     """

#     rows = fetch_all(
#         sql,
#         {
#             "organism_id": organism_id,
#             "effect_type": effect_type or None,
#             "top_n_chemicals": top_n_chemicals,
#             "top_n_effects": top_n_effects,
#         },
#     )

#     chemicals = sorted({row["chemical_label"] for row in rows})
#     endpoints = sorted({row["endpoint_label"] for row in rows})

#     value_map = {
#         (row["chemical_label"], row["endpoint_label"]): float(row["mean_value"])
#         for row in rows
#     }
#     n_conditions_map = {
#         (row["chemical_label"], row["endpoint_label"]): int(row["n_conditions"])
#         for row in rows
#     }
#     n_with_control_map = {
#         (row["chemical_label"], row["endpoint_label"]): int(row["n_with_control"])
#         for row in rows
#     }
#     n_without_control_map = {
#         (row["chemical_label"], row["endpoint_label"]): int(row["n_without_control"])
#         for row in rows
#     }

#     z = []
#     customdata = []

#     for chem in chemicals:
#         z_row = []
#         c_row = []
#         for endpoint in endpoints:
#             key = (chem, endpoint)
#             z_row.append(value_map.get(key, None))
#             c_row.append([
#                 n_conditions_map.get(key, 0),
#                 n_with_control_map.get(key, 0),
#                 n_without_control_map.get(key, 0),
#             ])
#         z.append(z_row)
#         customdata.append(c_row)

#     return jsonify({
#         "x": endpoints,
#         "y": chemicals,
#         "z": z,
#         "customdata": customdata,
#     })
