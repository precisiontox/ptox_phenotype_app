const dashboardData = document.getElementById("dashboard-data");
    const organismOverview = JSON.parse(dashboardData.dataset.organismOverview || "[]");
    const organismEffectType = JSON.parse(dashboardData.dataset.organismEffectType || "[]");

    const organismLabels = organismOverview.map(d =>
        d.common_name ? `${d.common_name} (${d.scientific_name})` : d.scientific_name
    );

    const nChemicals = organismOverview.map(d => d.n_chemicals);
    const nEndpoints = organismOverview.map(d => d.n_endpoints);
    const nExperiments = organismOverview.map(d => d.n_experiments);

    Plotly.newPlot("chemicals_by_organism", [{
        x: organismLabels,
        y: nChemicals,
        type: "bar"
    }], {
        title: "Chemicals",
        xaxis: { title: "Organism", automargin: true, tickangle: -35 },
        yaxis: { title: "Count" },
        margin: { l: 55, r: 10, t: 40, b: 120 }
    }, { responsive: true });

    Plotly.newPlot("effects_by_organism", [{
        x: organismLabels,
        y: nEndpoints,
        type: "bar"
    }], {
        title: "Endpoints",
        xaxis: { title: "Organism", automargin: true, tickangle: -35 },
        yaxis: { title: "Count" },
        margin: { l: 55, r: 10, t: 40, b: 120 }
    }, { responsive: true });

    Plotly.newPlot("experiments_by_organism", [{
        x: organismLabels,
        y: nExperiments,
        type: "bar"
    }], {
        title: "Experiments",
        xaxis: { title: "Organism", automargin: true, tickangle: -35 },
        yaxis: { title: "Count" },
        margin: { l: 55, r: 10, t: 40, b: 120 }
    }, { responsive: true });

    const organismTypeLabels = [...new Set(
        organismEffectType.map(d => d.common_name || d.scientific_name)
    )];

    const organismEndpointTypes = [...new Set(
        organismEffectType.map(d => d.effect_type)
    )];

    const effectTypeTraces = organismEndpointTypes.map(effectType => {
        const values = organismTypeLabels.map(label => {
            const row = organismEffectType.find(d => {
                const rowLabel = d.common_name || d.scientific_name;
                return rowLabel === label && d.effect_type === effectType;
            });
            return row ? row.n_endpoints : 0;
        });

        return {
            x: organismTypeLabels,
            y: values,
            type: "bar",
            name: effectType
        };
    });

    Plotly.newPlot("effect_types_by_organism", effectTypeTraces, {
        title: "Endpoint categories",
        barmode: "group",
        xaxis: { title: "Organism", automargin: true, tickangle: -35 },
        yaxis: { title: "Number of endpoints" },
        margin: { l: 60, r: 20, t: 50, b: 140 }
    }, { responsive: true });

    const table = document.getElementById("partner-effect-table");
    const tbody = table.querySelector("tbody");
    const headers = table.querySelectorAll("th");

    function applyFilters() {
        const partner = document.getElementById("filter-partner").value.toLowerCase();
        const organism = document.getElementById("filter-organism").value.toLowerCase();
        const effectType = document.getElementById("filter-effect-type").value.toLowerCase();

        Array.from(tbody.rows).forEach(row => {
            const cells = row.cells;
            const show =
                cells[0].innerText.toLowerCase().includes(partner) &&
                cells[1].innerText.toLowerCase().includes(organism) &&
                cells[2].innerText.toLowerCase().includes(effectType);

            row.style.display = show ? "" : "none";
        });
    }

    document.getElementById("filter-partner").addEventListener("input", applyFilters);
    document.getElementById("filter-organism").addEventListener("input", applyFilters);
    document.getElementById("filter-effect-type").addEventListener("input", applyFilters);

    headers.forEach((header, index) => {
        let ascending = true;
        header.style.cursor = "pointer";

        header.addEventListener("click", () => {
            const rows = Array.from(tbody.rows);

            rows.sort((a, b) => {
                const aText = a.cells[index].innerText.trim();
                const bText = b.cells[index].innerText.trim();
                const sortType = header.dataset.sort;

                let comparison = 0;

                if (sortType === "number") {
                    comparison = Number(aText) - Number(bText);
                } else {
                    comparison = aText.localeCompare(bText);
                }

                return ascending ? comparison : -comparison;
            });

            rows.forEach(row => tbody.appendChild(row));
            ascending = !ascending;
        });
    });
