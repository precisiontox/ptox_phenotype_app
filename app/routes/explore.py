from flask import Blueprint, render_template
from app.db import fetch_all

explore_bp = Blueprint("explore", __name__)


@explore_bp.route("/")
def index():
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

    col_desc = {
        "#": "Row index",
        "Endpoint Category": "High-level endpoint grouping",
        "Endpoint Name": "Original endpoint identifier",
        "Endpoint Value": "Value of the measurement for this endpoint",
        "Endpoint Unit": "Measurement unit for the endpoint",
        "Control": "Whether the sample is a control",
        "Chemical": "Tested chemical",
        "Exposure Concentration": "Exposure concentration and unit",
        "Sample type": "Source label for sample type (eg. type of control or exposure)",
        "Exposure Duration": "Exposure duration and unit at the time of endpoint measurement",
        "Stage Organism Exposure Start": "Developmental stage of organism(s) at time of exposure start",
        "Stage Organism Observation Start": "Developmental stage of organism(s) at time of observation start",
        "Container ID": "Container identifier (e.g. plate)",
        "Well ID": "Well or vessel identifier",
        "Batch ID": "Internal experiment batch identifier",
        "Partner": "Data-contributing partner",
        "Date": "Experiment date",
        "Biosystem Code": "PrecisionTox biosystem code (letter)",
        "Organism": "Scientific name of the organism",
        "Strain": "Organism strain or cell line",
        "Strain Generation": "Strain generation information",
        "Exposure Temperature": "Exposure temperature used in the experiment (in Celsius)",
        "Medium": "Exposure medium",
        "Solvent": "Solvent used in the experiment",
        "Solvent Proportion": "Proportion of solvent used",
        "Buffer": "Buffer used in the experiment",
        "Buffer Concentration": "Buffer concentration and unit",
        "Format": "Type of exposure vessel",
        "Test Volume per Well": "Test volume per well (in mL)",
        "Number Organisms or Cells": "Number of organisms or cells used",
        "Aggregated": "Whether the experiment data are aggregated",
        "Quality": "Quality flag associated with the experiment"
    }

    return render_template(
        "explore.html", 
        organisms=organisms,
        columnDes=col_desc
    )
