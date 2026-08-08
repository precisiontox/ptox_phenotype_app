import csv
import json
from pathlib import Path

from flask import Blueprint, jsonify, request
from app.db import fetch_all, fetch_one

api_bp = Blueprint("api", __name__)

TOXICITY_CATEGORIES_PATH = Path(__file__).resolve().parents[1] / "static" / "data" / "toxicity_categories.tsv"
CHEMICAL_GROUPS_PATH = Path(__file__).resolve().parents[1] / "static" / "data" / "chemical_groups.json"


def is_relevant_toxicity_association(score, n_refs):
    return score > 0 and (score >= 2 or (score >= 1 and n_refs >= 3))


def load_relevant_toxicity_categories():
    categories_by_ptx = {}
    if not TOXICITY_CATEGORIES_PATH.exists():
        return categories_by_ptx

    with TOXICITY_CATEGORIES_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            ptx_code = (row.get("ptx_code") or "").strip()
            tox_class = (row.get("tox_class") or "").strip()
            if not ptx_code or not tox_class:
                continue

            try:
                score = float(row.get("score") or 0)
                n_refs = int(float(row.get("n_refs") or 0))
            except ValueError:
                continue

            if is_relevant_toxicity_association(score, n_refs):
                categories_by_ptx.setdefault(ptx_code, {})[tox_class] = {
                    "score": score,
                    "n_refs": n_refs,
                }

    return categories_by_ptx


def load_chemical_groups():
    groups = {}
    if not CHEMICAL_GROUPS_PATH.exists():
        return groups

    with CHEMICAL_GROUPS_PATH.open(encoding="utf-8") as handle:
        for row in json.load(handle):
            ptx_code = (row.get("ptx_code") or "").strip()
            group_label = (row.get("group_label") or "").strip()
            if not ptx_code or not group_label:
                continue
            groups.setdefault(group_label, set()).add(ptx_code)

    return groups


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
    exposure_unit_check = {
        "has_mixed_units": False,
        "units": [],
    }

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

        exposure_unit_rows = fetch_all("""
            SELECT DISTINCT
                pc.exposure_concentration_unit
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
                AND pc.is_control = FALSE
                AND pc.exposure_concentration IS NOT NULL
                AND pc.exposure_concentration_unit IS NOT NULL
                AND TRIM(pc.exposure_concentration_unit) <> ''
            ORDER BY pc.exposure_concentration_unit
        """, {
            "organism_id": organism_id,
            "effect_type": effect_type,
            "endpoint_name": endpoint_name,
        })
        exposure_units = [row["exposure_concentration_unit"] for row in exposure_unit_rows]
        exposure_unit_check = {
            "has_mixed_units": len(exposure_units) > 1,
            "units": exposure_units,
        }

    return jsonify({
        "organism": organism_info,
        "category": category_info,
        "endpoint": endpoint_info,
        "exposure_unit_check": exposure_unit_check,
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
    ranking_mode = request.args.get("ranking_mode", default="mean_response", type=str)
    ranking_mode = ranking_mode if ranking_mode in {
        "response_at_max",
        "mean_response",
        "max_response",
        "pod",
    } else "mean_response"

    if not organism_id or not effect_type or not endpoint_name:
        return jsonify({"rows": [], "endpoint_label": None, "endpoint_unit": None})

    order_clause = "mean_value DESC, chemical_name"

    if ranking_mode == "pod":
        order_clause = "mean_value ASC, chemical_name"
        aggregation_cte = """
        WITH numeric_records AS (
            SELECT
                c.ptx_code,
                c.full_ptx_code,
                c.name AS chemical_name,
                pe.phenotype_experiment_id,
                pe.internal_experiment_batch_id AS batch_id,
                pef.display_name AS endpoint_label,
                pef.unit AS endpoint_unit,
                pc.is_control,
                pc.exposure_concentration,
                pc.exposure_concentration_unit,
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
        control_stats AS (
            SELECT
                phenotype_experiment_id,
                batch_id,
                AVG(value_num) AS control_mean,
                STDDEV_SAMP(value_num) AS control_sd,
                COUNT(*) AS n_control
            FROM numeric_records
            WHERE is_control = TRUE
            GROUP BY phenotype_experiment_id, batch_id
        ),
        exposure_stats AS (
            SELECT
                ptx_code,
                full_ptx_code,
                chemical_name,
                phenotype_experiment_id,
                batch_id,
                exposure_concentration,
                exposure_concentration_unit,
                AVG(value_num) AS exposure_mean
            FROM numeric_records
            WHERE is_control = FALSE
              AND ptx_code IS NOT NULL
              AND exposure_concentration IS NOT NULL
            GROUP BY
                ptx_code,
                full_ptx_code,
                chemical_name,
                phenotype_experiment_id,
                batch_id,
                exposure_concentration,
                exposure_concentration_unit
        ),
        pod_candidates AS (
            SELECT
                es.full_ptx_code,
                es.chemical_name,
                es.exposure_concentration,
                es.exposure_concentration_unit
            FROM exposure_stats es
            JOIN control_stats cs
              ON es.phenotype_experiment_id = cs.phenotype_experiment_id
             AND es.batch_id IS NOT DISTINCT FROM cs.batch_id
            WHERE
                ABS(es.exposure_mean - cs.control_mean) >=
                    CASE
                        WHEN cs.control_sd IS NOT NULL AND cs.control_sd > 0
                            THEN 2 * cs.control_sd
                        WHEN cs.control_mean <> 0
                            THEN ABS(cs.control_mean) * 0.2
                        ELSE NULL
                    END
        ),
        endpoint_at_max AS (
            SELECT
                full_ptx_code,
                chemical_name,
                'Empirical PoD' AS endpoint_label,
                exposure_concentration_unit AS endpoint_unit,
                MIN(exposure_concentration) AS mean_value
            FROM pod_candidates
            GROUP BY
                full_ptx_code,
                chemical_name,
                exposure_concentration_unit
        )
        """
    elif ranking_mode == "response_at_max":
        aggregation_cte = """
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
        """
    else:
        metric_expr = "AVG(value_num)" if ranking_mode == "mean_response" else "MAX(value_num)"
        aggregation_cte = f"""
        WITH numeric_records AS (
            SELECT
                c.ptx_code,
                c.full_ptx_code,
                c.name AS chemical_name,
                pef.display_name AS endpoint_label,
                pef.unit AS endpoint_unit,
                pc.is_control,
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
                AND pc.is_control = FALSE
                AND c.ptx_code IS NOT NULL
        ),
        endpoint_at_max AS (
            SELECT
                full_ptx_code,
                chemical_name,
                endpoint_label,
                endpoint_unit,
                {metric_expr} AS mean_value
            FROM numeric_records
            GROUP BY
                full_ptx_code,
                chemical_name,
                endpoint_label,
                endpoint_unit
        )
        """

    rows = fetch_all(f"""
        {aggregation_cte}
        SELECT
            full_ptx_code,
            chemical_name,
            endpoint_label,
            endpoint_unit,
            mean_value
        FROM endpoint_at_max
        ORDER BY {order_clause}
    """, {
        "organism_id": organism_id,
        "effect_type": effect_type,
        "endpoint_name": endpoint_name,
    })

    endpoint_labels = {row["endpoint_label"] for row in rows if row["endpoint_label"]}
    endpoint_units = {row["endpoint_unit"] for row in rows if row["endpoint_unit"]}
    endpoint_label = next(iter(endpoint_labels)) if len(endpoint_labels) == 1 else endpoint_name
    endpoint_unit = next(iter(endpoint_units)) if len(endpoint_units) == 1 else None

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


@api_bp.route("/compare/toxicity-categories")
def compare_toxicity_categories():
    organism_id = request.args.get("organism_id", type=int)
    if not organism_id:
        return jsonify({"categories": []})

    chemical_rows = fetch_all("""
        SELECT DISTINCT
            c.full_ptx_code
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
            AND (
                pc.sample_type IS NULL
                OR pc.sample_type <> 'no_cells'
            )
    """, {"organism_id": organism_id})

    available_ptx_codes = {row["full_ptx_code"] for row in chemical_rows}
    categories_by_ptx = load_relevant_toxicity_categories()
    category_counts = {}

    for ptx_code in available_ptx_codes:
        for tox_class in categories_by_ptx.get(ptx_code, {}):
            category_counts[tox_class] = category_counts.get(tox_class, 0) + 1

    categories = [
        {"tox_class": tox_class, "n_chemicals": n_chemicals}
        for tox_class, n_chemicals in sorted(category_counts.items())
    ]
    return jsonify({"categories": categories})


@api_bp.route("/compare/rr-groups")
def compare_rr_groups():
    organism_id = request.args.get("organism_id", type=int)
    if not organism_id:
        return jsonify({"groups": []})

    chemical_rows = fetch_all("""
        SELECT DISTINCT
            c.full_ptx_code
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
            AND (
                pc.sample_type IS NULL
                OR pc.sample_type <> 'no_cells'
            )
    """, {"organism_id": organism_id})

    available_ptx_codes = {row["full_ptx_code"] for row in chemical_rows}
    rr_groups = load_chemical_groups()
    groups = []
    for group_name, ptx_codes in sorted(rr_groups.items()):
        n_chemicals = len(ptx_codes & available_ptx_codes)
        if n_chemicals:
            groups.append({"group_name": group_name, "n_chemicals": n_chemicals})

    return jsonify({"groups": groups})

@api_bp.route("/compare/heatmap")
def compare_heatmap():
    organism_id = request.args.get("organism_id", type=int)
    effect_type = request.args.get("effect_type", type=str)
    endpoint_name = request.args.get("endpoint_name", type=str)
    metric = request.args.get("metric", default="difference", type=str)
    clustering = request.args.get("clustering", default="hierarchical", type=str)
    toxicity_category = request.args.get("toxicity_category", type=str)
    rr_group = request.args.get("rr_group", type=str)
    if clustering not in {"default", "nearest-neighbor", "hierarchical"}:
        clustering = "hierarchical"

    if not organism_id:
        return jsonify({
            "x": [],
            "y": [],
            "z": [],
            "customdata": [],
            "metric": metric,
            "clustering": clustering,
            "toxicity_category": toxicity_category,
            "rr_group": rr_group,
        })

    metric_type_map = {
        "difference": "difference",
        "zscore": "z-score",
        "response_score": "dose-response evidence",
    }
    if metric not in metric_type_map:
        metric = "difference"
    metric_type = metric_type_map[metric]

    rows = fetch_all("""
        SELECT
            CONCAT('[', c.full_ptx_code, '] ', c.name) AS chemical_label,
            CONCAT(
                '[',
                pef.type,
                '] ',
                pef.display_name,
                CASE
                    WHEN m.exposure_duration IS NOT NULL
                        THEN CONCAT(' (', m.exposure_duration::TEXT, 'h)')
                    ELSE ''
                END
            ) AS endpoint_label,
            AVG(m.metric_value) AS mean_value,
            SUM(m.n_experiments) AS n_experiments,
            SUM(m.n_with_control) AS n_with_control,
            SUM(m.n_without_control) AS n_without_control
        FROM mv_compare_heatmap_metrics m
        JOIN chemical c
          ON m.ptx_code = c.ptx_code
        JOIN phenotype_effect pef
          ON m.phenotype_effect_id = pef.phenotype_effect_id
        JOIN biosystem b
          ON pef.biosystem_id = b.biosystem_id
        WHERE
            b.organism_id = :organism_id
            AND m.metric_type = :metric_type
            AND (:effect_type IS NULL OR pef.type = :effect_type)
            AND (:endpoint_name IS NULL OR pef.name = :endpoint_name)
        GROUP BY
            c.full_ptx_code,
            c.name,
            pef.type,
            pef.display_name,
            m.exposure_duration
        ORDER BY
            c.full_ptx_code,
            c.name,
            pef.type,
            pef.display_name,
            m.exposure_duration NULLS FIRST
    """, {
        "organism_id": organism_id,
        "metric_type": metric_type,
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
            AND (
                pc.sample_type IS NULL
                OR pc.sample_type <> 'no_cells'
            )
        ORDER BY c.full_ptx_code, c.name
    """, {"organism_id": organism_id})

    if not rows:
        return jsonify({
            "x": [],
            "y": [],
            "z": [],
            "customdata": [],
            "metric": metric,
            "clustering": clustering,
            "toxicity_category": toxicity_category,
            "rr_group": rr_group,
        })

    if toxicity_category:
        categories_by_ptx = load_relevant_toxicity_categories()
        chemical_rows = [
            row for row in chemical_rows
            if toxicity_category in categories_by_ptx.get(row["full_ptx_code"], {})
        ]

    if rr_group:
        rr_groups = load_chemical_groups()
        selected_ptx_codes = rr_groups.get(rr_group, set())
        chemical_rows = [
            row for row in chemical_rows
            if row["full_ptx_code"] in selected_ptx_codes
        ]

    chemicals = [f'[{r["full_ptx_code"]}] {r["name"]}' for r in chemical_rows]
    endpoints = sorted({r["endpoint_label"] for r in rows})

    if not chemicals:
        return jsonify({
            "x": [],
            "y": [],
            "z": [],
            "customdata": [],
            "metric": metric,
            "clustering": clustering,
            "toxicity_category": toxicity_category,
            "rr_group": rr_group,
        })

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

    normalized = [row[:] for row in z]
    for j in range(len(endpoints)):
        vals = [normalized[i][j] for i in range(len(chemicals)) if normalized[i][j] is not None]
        if not vals:
            continue

        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        sd = math.sqrt(variance)

        for i in range(len(chemicals)):
            value = normalized[i][j]
            if value is None:
                normalized[i][j] = None
            elif sd == 0:
                normalized[i][j] = 0.0
            else:
                normalized[i][j] = (value - mean) / sd

    filled = [
        [value if value is not None else 0.0 for value in row]
        for row in normalized
    ]

    def euclidean(row_a, row_b):
        return math.sqrt(sum((row_a[k] - row_b[k]) ** 2 for k in range(len(endpoints))))

    def nearest_neighbor_order(vectors):
        remaining = list(range(len(vectors)))
        order = []
        row_means = [sum(row) / len(row) if row else 0 for row in vectors]
        start = min(remaining, key=lambda i: row_means[i]) if remaining else None
        if start is not None:
            order.append(start)
            remaining.remove(start)

        while remaining:
            last = order[-1]
            nxt = min(remaining, key=lambda i: euclidean(vectors[last], vectors[i]))
            order.append(nxt)
            remaining.remove(nxt)

        return order

    def hierarchical_cluster(vectors):
        if not vectors:
            return [], []
        if len(vectors) == 1:
            return [0], []

        clusters = {
            i: {
                "id": i,
                "members": [i],
                "left": None,
                "right": None,
                "height": 0.0,
                "size": 1,
            }
            for i in range(len(vectors))
        }
        active = list(clusters)
        next_id = len(vectors)
        distances = {}
        for idx, a_id in enumerate(active[:-1]):
            for b_id in active[idx + 1:]:
                distances[(a_id, b_id)] = euclidean(vectors[a_id], vectors[b_id])

        def distance_between(a_id, b_id):
            key = (a_id, b_id) if a_id < b_id else (b_id, a_id)
            return distances[key]

        while len(active) > 1:
            best = None
            for idx, a_id in enumerate(active[:-1]):
                for b_id in active[idx + 1:]:
                    distance = distance_between(a_id, b_id)
                    candidate = (
                        distance,
                        min(clusters[a_id]["members"]),
                        min(clusters[b_id]["members"]),
                        a_id,
                        b_id,
                    )
                    if best is None or candidate < best:
                        best = candidate

            distance, _, _, left_id, right_id = best
            left = clusters[left_id]
            right = clusters[right_id]
            if min(right["members"]) < min(left["members"]):
                left_id, right_id = right_id, left_id
                left = clusters[left_id]
                right = clusters[right_id]

            clusters[next_id] = {
                "id": next_id,
                "members": left["members"] + right["members"],
                "left": left_id,
                "right": right_id,
                "height": distance,
                "size": left["size"] + right["size"],
            }
            next_active = [cluster_id for cluster_id in active if cluster_id not in (left_id, right_id)]
            for other_id in next_active:
                merged_distance = (
                    left["size"] * distance_between(left_id, other_id)
                    + right["size"] * distance_between(right_id, other_id)
                ) / (left["size"] + right["size"])
                key = (other_id, next_id) if other_id < next_id else (next_id, other_id)
                distances[key] = merged_distance

            active = next_active
            active.append(next_id)
            next_id += 1

        root_id = active[0]

        def leaves(node_id):
            node = clusters[node_id]
            if node["left"] is None:
                return node["members"]
            return leaves(node["left"]) + leaves(node["right"])

        order = leaves(root_id)
        leaf_positions = {leaf_id: pos for pos, leaf_id in enumerate(order)}
        segments = []

        def build_segments(node_id):
            node = clusters[node_id]
            if node["left"] is None:
                return leaf_positions[node_id], 0.0

            left_y, left_height = build_segments(node["left"])
            right_y, right_height = build_segments(node["right"])
            height = node["height"]
            segments.append({
                "x": [left_height, height, height, right_height],
                "y": [left_y, left_y, right_y, right_y],
            })
            return (left_y + right_y) / 2, height

        build_segments(root_id)
        return order, segments

    dendrogram_segments = []
    if clustering == "hierarchical":
        order, dendrogram_segments = hierarchical_cluster(filled)
    elif clustering == "nearest-neighbor":
        order = nearest_neighbor_order(filled)
    else:
        order = list(range(len(chemicals)))

    chemicals_ordered = [chemicals[i] for i in order]
    z_ordered = [z[i] for i in order]
    custom_ordered = [customdata[i] for i in order]

    return jsonify({
        "x": endpoints,
        "y": chemicals_ordered,
        "z": z_ordered,
        "customdata": custom_ordered,
        "dendrogram": dendrogram_segments,
        "metric": metric,
        "clustering": clustering,
        "toxicity_category": toxicity_category,
        "rr_group": rr_group,
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
            pc.sample_type,
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
            AND (
                pc.sample_type IS NULL
                OR pc.sample_type <> 'no_cells'
            )
            AND (
                pc.is_control IS NOT TRUE
                OR pc.sample_type IS NULL
                OR pc.sample_type NOT ILIKE '%agonist%'
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
