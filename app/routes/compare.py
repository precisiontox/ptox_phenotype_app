from flask import Blueprint, render_template
from app.db import fetch_all

compare_bp = Blueprint("compare", __name__)


@compare_bp.route("/")
def heatmap():
    organisms = fetch_all("""
        SELECT DISTINCT
            o.organism_id,
            o.scientific_name,
            o.common_name,
            o.uniprot_acronym
        FROM phenotype_experiment pe
        JOIN biosystem b
          ON pe.biosystem_id = b.biosystem_id
        JOIN organism o
          ON b.organism_id = o.organism_id
        ORDER BY o.scientific_name
    """)

    return render_template("compare.html", organisms=organisms)
    