let exploreTable = null;
let exploreTableShowAll = false;

function getSelections() {
    return {
        organism_id: document.getElementById("organism-select").value,
        effect_type: document.getElementById("category-select").value,
        endpoint_name: document.getElementById("endpoint-select").value,
        ptx_code: document.getElementById("chemical-select").value
    };
}

function getRankingMode() {
    return document.getElementById("ranking-mode-select").value || "mean_response";
}

function updateExposureUnitWarning(unitCheck) {
    const warningBox = document.getElementById("exposure-unit-warning");
    if (!unitCheck || !unitCheck.has_mixed_units) {
        warningBox.hidden = true;
        warningBox.textContent = "";
        return;
    }

    const units = (unitCheck.units || []).map(unit => String(unit));
    warningBox.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = "Exposure concentration unit warning: ";
    warningBox.append(
        title,
        `this endpoint contains records with multiple chemical exposure concentration units (${units.join(", ")}). `,
        "Ranking and dose-response plots compare raw concentration values, so interpret these results with care."
    );
    warningBox.hidden = false;
}

function applyHeaderTooltips(api) {
    const tableElement = document.getElementById("explore-table");
    const columnDescriptions = JSON.parse(tableElement.dataset.columnDescriptions || "{}");
    const visibleHeader = $(api.table().container()).find('.dataTables_scrollHead thead tr:first-child th');

    visibleHeader.each(function() {
        const headerText = $(this).text().trim();
        if (columnDescriptions[headerText]) {
            $(this).attr('title', columnDescriptions[headerText]);
        }
    });
}

function updateUrlFromSelections() {
    const { organism_id, effect_type, endpoint_name, ptx_code } = getSelections();
    const params = new URLSearchParams();

    if (organism_id) params.set("organism_id", organism_id);
    if (effect_type) params.set("effect_type", effect_type);
    if (endpoint_name) params.set("endpoint_name", endpoint_name);
    if (ptx_code) params.set("ptx_code", ptx_code);
    if (getRankingMode() !== "mean_response") params.set("ranking_mode", getRankingMode());
    if (document.getElementById("dose-log-scale").checked) params.set("log_x", "1");

    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, "", newUrl);
}

function applySelectionsFromUrl() {
    const params = new URLSearchParams(window.location.search);

    const organism_id = params.get("organism_id") || "";
    const effect_type = params.get("effect_type") || "";
    const endpoint_name = params.get("endpoint_name") || "";
    const ptx_code = params.get("ptx_code") || "";
    const ranking_mode = params.get("ranking_mode") || "mean_response";
    const log_x = params.get("log_x") === "1";

    document.getElementById("organism-select").value = organism_id;
    if ([...document.getElementById("ranking-mode-select").options].some(opt => opt.value === ranking_mode)) {
        document.getElementById("ranking-mode-select").value = ranking_mode;
    }
    document.getElementById("dose-log-scale").checked = log_x;

    return { effect_type, endpoint_name, ptx_code };
}

async function loadOptions() {
    const organismId = document.getElementById("organism-select").value;
    const currentCategory = document.getElementById("category-select").value;
    const currentEndpoint = document.getElementById("endpoint-select").value;
    const currentChemical = document.getElementById("chemical-select").value;

    const categorySelect = document.getElementById("category-select");
    const endpointSelect = document.getElementById("endpoint-select");
    const chemicalSelect = document.getElementById("chemical-select");

    if (!organismId) {
        categorySelect.innerHTML = '<option value="">All</option>';
        endpointSelect.innerHTML = '<option value="">All</option>';
        chemicalSelect.innerHTML = '<option value="">All chemicals</option>';
        categorySelect.disabled = true;
        endpointSelect.disabled = true;
        chemicalSelect.disabled = true;
        return;
    }

    const params = new URLSearchParams({ organism_id: organismId });
    if (currentCategory) params.append("effect_type", currentCategory);
    if (currentEndpoint) params.append("endpoint_name", currentEndpoint);

    const response = await fetch(`${window.APP_ROOT}/api/explore/options?${params.toString()}`);
    const data = await response.json();

    categorySelect.innerHTML =
        '<option value="">Select endpoint category...</option>' +
        data.categories.map(x => `<option value="${x.effect_type}">${x.effect_type}</option>`).join("");

    endpointSelect.innerHTML =
        '<option value="">Select endpoint...</option>' +
        data.endpoints.map(x => `<option value="${x.endpoint_name}">${x.endpoint_display_name}</option>`).join("");

    chemicalSelect.innerHTML =
        '<option value="">All chemicals</option>' +
        data.chemicals.map(x => `<option value="${x.ptx_code}">[${x.full_ptx_code}] ${x.name}</option>`).join("");

    categorySelect.disabled = false;
    endpointSelect.disabled = false;
    chemicalSelect.disabled = false;

    // Restore selected values if still valid
    if ([...categorySelect.options].some(opt => opt.value === currentCategory)) {
        categorySelect.value = currentCategory;
    }

    if ([...endpointSelect.options].some(opt => opt.value === currentEndpoint)) {
        endpointSelect.value = currentEndpoint;
    }

    if ([...chemicalSelect.options].some(opt => opt.value === currentChemical)) {
        chemicalSelect.value = currentChemical;
    }
}

async function loadInfoPanels() {
    const { organism_id, effect_type, endpoint_name } = getSelections();

    const organismBox = document.getElementById("organism-info");
    const categoryBox = document.getElementById("category-info");
    const endpointBox = document.getElementById("endpoint-info");

    if (!organism_id) {
        organismBox.innerHTML = '<span class="text-muted">Select an organism.</span>';
        categoryBox.innerHTML = '<span class="text-muted">Select an endpoint category.</span>';
        endpointBox.innerHTML = '<span class="text-muted">Select an endpoint.</span>';
        updateExposureUnitWarning(null);
        return;
    }

    const params = new URLSearchParams({ organism_id });
    if (effect_type) params.append("effect_type", effect_type);
    if (endpoint_name) params.append("endpoint_name", endpoint_name);

    const response = await fetch(`${window.APP_ROOT}/api/explore/info?${params.toString()}`);
    const data = await response.json();
    updateExposureUnitWarning(data.exposure_unit_check);

    if (data.organism) {
        organismBox.innerHTML = `
            <div class="info-row"><span class="info-label">Scientific name:</span><strong> ${data.organism.scientific_name || ""}</strong></div>
            <div class="info-row"><span class="info-label">Biosystem code:</span> ${data.organism.biosystem_code || ""}</div>
            <div class="info-row"><span class="info-label">UniProt acronym:</span> ${data.organism.uniprot_acronym || ""}</div>
            <div class="info-row"><span class="info-label">NCBI tax ID:</span> ${data.organism.ncbi_tax_id || ""}</div>
        `;
    } else {
        organismBox.innerHTML = "No organism information available.";
    }

    if (data.category) {
        categoryBox.innerHTML = `
            <div class="info-row"><span class="info-label">Category:</span><strong> ${data.category.effect_type || ""}</strong></div>
            <div class="info-row"><span class="info-label">Description:</span> ${data.category.type_description || ""}</div>
            <div class="info-row"><span class="info-label">Number of endpoints:</span> ${data.category.n_endpoints || 0}</div>
        `;
    } else {
        categoryBox.innerHTML = "Select an endpoint category.";
    }

    if (data.endpoint) {
        endpointBox.innerHTML = `
            <div class="info-row"><span class="info-label">Display name:</span><strong> ${data.endpoint.display_name || ""} </strong></div>
            <div class="info-row"><span class="info-label">Original name:</span> ${data.endpoint.name || ""}</div>
            <div class="info-row"><span class="info-label">Ontology term:</span> ${data.endpoint.ontology_term || ""}</div>
            <div class="info-row"><span class="info-label">Description:</span> ${data.endpoint.description || ""}</div>
            <div class="info-row"><span class="info-label">Unit:</span> ${data.endpoint.unit || ""}</div>
            <div class="info-row"><span class="info-label">Data type:</span> ${data.endpoint.data_type || ""}</div>
        `;
    } else {
        endpointBox.innerHTML = "Select an endpoint.";
    }
}

async function loadHistogram() {
    const { organism_id, effect_type, endpoint_name } = getSelections();

    if (!organism_id || !effect_type || !endpoint_name) {
        Plotly.newPlot("histogram", [], {
            title: {
                text: "Select organism, endpoint category and endpoint",
                font: {
                    size: 14
                }
            },
            xaxis: { visible: false },
            yaxis: { visible: false }
        }, { responsive: true });
        return;
    }

    const params = new URLSearchParams({ organism_id, effect_type, endpoint_name });
    const response = await fetch(`${window.APP_ROOT}/api/explore/histogram?${params.toString()}`);
    const data = await response.json();

    const traces = [
        {
            x: data.control_values,
            type: "histogram",
            histnorm: "probability density",
            name: `Control (n=${data.n_control})`,
            opacity: 0.6
        },
        {
            x: data.exposure_values,
            type: "histogram",
            histnorm: "probability density",
            name: `Exposure (n=${data.n_exposure})`,
            opacity: 0.6
        }
    ];

    const shapes = [];
    if (data.control_mean !== null) {
        shapes.push({
            type: "line",
            x0: data.control_mean,
            x1: data.control_mean,
            y0: 0,
            y1: 1,
            xref: "x",
            yref: "paper",
            line: { dash: "dash", width: 2 }
        });
    }
    if (data.exposure_mean !== null) {
        shapes.push({
            type: "line",
            x0: data.exposure_mean,
            x1: data.exposure_mean,
            y0: 0,
            y1: 1,
            xref: "x",
            yref: "paper",
            line: { dash: "dot", width: 2 }
        });
    }

    let xTitle = data.endpoint_label || "Endpoint value";
    if (data.endpoint_unit) {
        xTitle = `${xTitle} (${data.endpoint_unit})`;
    }

    Plotly.newPlot("histogram", traces, {
        title: "Endpoint distribution",
        barmode: "overlay",
        xaxis: { title: xTitle },
        yaxis: { title: "Density" },
        shapes: shapes,
        margin: { l: 60, r: 20, t: 50, b: 60 }
    }, { responsive: true });
}

async function loadRanking() {
    const { organism_id, effect_type, endpoint_name } = getSelections();
    const rankingMode = getRankingMode();

    if (!organism_id || !effect_type || !endpoint_name) {
        Plotly.newPlot("ranking-plot", [], {
            title: {
                text: "Select organism, endpoint category and endpoint",
                font: {
                    size: 14
                }
            },
            xaxis: { visible: false },
            yaxis: { visible: false }
        }, { responsive: true });
        return;
    }

    const params = new URLSearchParams({ organism_id, effect_type, endpoint_name, ranking_mode: rankingMode });
    const response = await fetch(`${window.APP_ROOT}/api/explore/ranking?${params.toString()}`);
    const data = await response.json();

    if (!data.rows.length) {
        Plotly.newPlot("ranking-plot", [], {
            title: "No ranking data available for the selected filters",
            xaxis: { visible: false },
            yaxis: { visible: false }
        }, { responsive: true });
        return;
    }

    const labels = data.rows.map(r => `[${r.full_ptx_code}] ${r.chemical_name}`);
    const values = data.rows.map(r => r.mean_value);

    let yTitle = data.endpoint_label || "Endpoint value";
    if (data.endpoint_unit) {
        yTitle = `${yTitle} (${data.endpoint_unit})`;
    }

    const rankingTitles = {
        mean_response: "Chemicals ranked by mean response",
        pod: "Chemicals ranked by empirical point of departure",
        max_response: "Chemicals ranked by maximum recorded response",
        response_at_max: "Chemicals ranked by response at highest tested concentration"
    };

    Plotly.newPlot("ranking-plot", [{
        x: labels,
        y: values,
        type: "bar"
    }], {
        title: rankingTitles[rankingMode] || "Chemical ranking",
        xaxis: { title: "Chemical", tickangle: -45, automargin: true },
        yaxis: { title: yTitle },
        margin: { l: 60, r: 20, t: 50, b: 180 }
    }, { responsive: true });
}

async function loadDoseResponse() {
    const { organism_id, effect_type, endpoint_name, ptx_code } = getSelections();
    const container = document.getElementById("dose-response-container");
    const chemicalSelect = document.getElementById("chemical-select");
    const chemicalLabel = chemicalSelect.options[chemicalSelect.selectedIndex]?.text || "";

    if (!organism_id || !effect_type || !endpoint_name || !ptx_code) {
        container.innerHTML = '<div id="dose-response-empty" class="chart-box chart-box-placeholder"></div>';

        Plotly.newPlot("dose-response-empty", [], {
            title: {
                text: "Select organism, endpoint category, endpoint and chemical",
                font: {
                    size: 14
                }
            },
            xaxis: { visible: false },
            yaxis: { visible: false }
        }, { responsive: true });
        return;
    }

    const params = new URLSearchParams({ organism_id, effect_type, endpoint_name, ptx_code });
    const response = await fetch(`${window.APP_ROOT}/api/explore/dose_response?${params.toString()}`);
    const data = await response.json();

    if (!data.series.length) {
        container.innerHTML = '<div id="dose-response-empty" class="chart-box chart-box-placeholder"></div>';

        Plotly.newPlot("dose-response-empty", [], {
            title: "No dose-response data available for the selected filters",
            xaxis: { visible: false },
            yaxis: { visible: false }
        }, { responsive: true });
        return;
    }

    const durationGroups = {};
    data.series.forEach(series => {
        const durationKey = series.duration_label && series.duration_label.trim() !== ""
            ? series.duration_label
            : "No duration specified";

        if (!durationGroups[durationKey]) {
            durationGroups[durationKey] = [];
        }
        durationGroups[durationKey].push(series);
    });

    function durationSortKey(label) {
        if (label === "No duration specified") return Number.POSITIVE_INFINITY;
        const match = label.match(/[-+]?\d*\.?\d+/);
        return match ? parseFloat(match[0]) : Number.POSITIVE_INFINITY;
    }

    const durationKeys = Object.keys(durationGroups).sort((a, b) => {
        const ka = durationSortKey(a);
        const kb = durationSortKey(b);
        if (ka !== kb) return ka - kb;
        return a.localeCompare(b);
    });

    container.innerHTML = durationKeys.map((duration, idx) => `
        <div id="dose-response-${idx}" class="chart-box chart-box-placeholder"></div>
    `).join("");

    const isLogX = document.getElementById("dose-log-scale").checked;
    const xBaseTitle = data.x_unit ? `Concentration (${data.x_unit})` : "Concentration";
    const xTitle = isLogX ? `log10 ${xBaseTitle}` : xBaseTitle;

    let yTitle = data.endpoint_label || "Endpoint value";
    if (data.y_unit) {
        yTitle = `${yTitle} (${data.y_unit})`;
    }

    function lightenColor(hex, factor = 0.5) {
        const num = parseInt(hex.slice(1), 16);
        let r = (num >> 16) + Math.floor((255 - (num >> 16)) * factor);
        let g = ((num >> 8) & 0x00FF) + Math.floor((255 - ((num >> 8) & 0x00FF)) * factor);
        let b = (num & 0x0000FF) + Math.floor((255 - (num & 0x0000FF)) * factor);
        return `rgb(${r},${g},${b})`;
    }

    durationKeys.forEach((duration, idx) => {
        const traces = [];
        const colors = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
            "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
            "#bcbd22", "#17becf"
        ];

        durationGroups[duration].forEach((series, i) => {
            let seriesLabel = "";
            const showSeriesLabel = durationGroups[duration].length > 1;
            const color = colors[i % colors.length];

            if (showSeriesLabel) {
                if (series.batch_id) {
                    seriesLabel = ` (Batch ID=${series.batch_id}`;
                } else if (series.exp_id) {
                    seriesLabel = ` (Exp ID=${series.exp_id}`;
                }

                if (series.experiment_date) {
                    seriesLabel += `; Date=${series.experiment_date})`;
                } else {
                    seriesLabel += `)`;
                }
            }
            traces.push({
                x: series.x,
                y: series.y,
                error_y: {
                    type: "data",
                    array: series.sem,
                    visible: true
                },
                mode: "lines+markers",
                type: "scatter",
                name: `Exposure${seriesLabel}`,
                line: { color: color },
                marker: { color: color },
                customdata: series.n_conditions,
                hovertemplate:
                    "Concentration: %{x}<br>" +
                    "Mean: %{y}<br>" +
                    "SEM: %{error_y.array}<br>" +
                    "N conditions: %{customdata}<extra></extra>"
                });

            if (series.control_mean !== null && series.x.length > 0) {
                const minX = Math.min(...series.x);
                const maxX = Math.max(...series.x);

                traces.push({
                    x: [minX, maxX],
                    y: [series.control_mean, series.control_mean],
                    mode: "lines",
                    type: "scatter",
                    line: { dash: "dash", color: lightenColor(color, 0.5) },
                    name: `Control${seriesLabel}`,
                    hovertemplate: `${seriesLabel}<br>Control mean: %{y}<extra></extra>`
                });
            }
        });

        Plotly.newPlot(`dose-response-${idx}`, traces, {
            title: {
                text: `Dose-response — ${chemicalLabel}<br>${duration}`,
                font: { size: 13}
            },
            xaxis: {
                title: xTitle,
                type: document.getElementById("dose-log-scale").checked ? "log" : "linear"
            },
            yaxis: { title: yTitle },
            margin: { l: 60, r: 20, t: 50, b: 60 },
            legend: {
                orientation: "h",
                y: -0.25
            }
        }, { responsive: true });
    });
}


async function loadTable() {
    const { organism_id, effect_type, endpoint_name, ptx_code } = getSelections();

    if (!organism_id) {
        if (exploreTable) {
            exploreTable.destroy();
            exploreTable = null;
        }
        $('#explore-table tbody').empty();
        return;
    }

    const params = new URLSearchParams({ organism_id });
    if (effect_type) params.append("effect_type", effect_type);
    if (endpoint_name) params.append("endpoint_name", endpoint_name);
    if (ptx_code) params.append("ptx_code", ptx_code);
    if (exploreTableShowAll) params.append("show_all", "1");


    const response = await fetch(`${window.APP_ROOT}/api/explore/table?${params.toString()}`);
    const data = await response.json();

    const note = document.getElementById("explore-table-note");
    const showAllBtn = document.getElementById("show-all-table-btn");

    if (data.is_truncated) {
        note.textContent = "Showing first 5000 records. Click 'Show everything' to load all matching rows.";
        showAllBtn.style.display = "inline-block";
    } else {
        note.textContent = exploreTableShowAll ? "Showing all matching records." : "";
        showAllBtn.style.display = "none";
    }

    const rows = data.rows.map(r => [
        r.phenotype_record_id,
        r.endpoint_category || "",
        r.endpoint_name || "",
        r.effect_value || "",
        r.endpoint_unit || "",
        r.is_control,
        r.full_ptx_code ? `[${r.full_ptx_code}] ${r.chemical_name}` : "",
        r.exposure_concentration !== null
            ? `${r.exposure_concentration} ${r.exposure_concentration_unit || ""}`.trim()
            : "",
        r.sample_type || "",
        r.exposure_duration !== null
            ? `${r.exposure_duration}${r.exposure_duration_unit || ""}`.trim()
            : "",
        r.stage_exp !== null
            ? `${r.stage_exp} ${r.stage_unit || ""}`.trim()
            : "",
        r.stage_obs !== null
            ? `${r.stage_obs} ${r.stage_unit || ""}`.trim()
            : "",
        r.container_id || "",
        r.well_name || "",
        r.internal_experiment_batch_id || "",
        r.partner_id || "",
        r.experiment_date || "",
        r.biosystem_code || "",
        r.organism || "",
        r.strain || "",
        r.strain_generation || "",
        r.exposure_temperature !== null
            ? `${r.exposure_temperature}°C`.trim()
            : "",
        r.medium || "",
        r.solvent || "",
        r.solvent_proportion || "",
        r.buffer || "",
        r.buffer_concentration !== null
            ? `${r.buffer_concentration} ${r.buffer_concentration_unit || ""}`.trim()
            : "",
        r.format_exposure || "",
        r.test_vol !== null
            ? `${r.test_vol}mL`.trim()
            : "",
        r.num_org || "",
        r.aggregated_data,
        r.quality_flag || ""
    ]);

    if (exploreTable) {
        exploreTable.destroy();
        exploreTable = null;
    }

    $('#explore-table tbody').empty();

    exploreTable = $('#explore-table').DataTable({
        data: rows,
        pageLength: 25,
        lengthMenu: [10, 25, 50, 100],
        scrollX: true,
        destroy: true,
        dom: 'Bfrtip',
        buttons: [
            {
                extend: 'csvHtml5',
                text: 'Export CSV',
                title: 'precisiontox_explore_records'
            }
        ],
        columnDefs: [
            { orderable: false, targets: 0, className: "no-sort" }
        ],
        initComplete: function () {
            const api = this.api();
            const visibleHeader = $(api.table().container()).find('.dataTables_scrollHead thead tr:first-child th');

            const groupClasses = [
                "th-group-record",
                "th-group-record",
                "th-group-record",
                "th-group-record",
                "th-group-record",
                "th-group-condition",
                "th-group-condition",
                "th-group-condition",
                "th-group-condition",
                "th-group-condition",
                "th-group-condition",
                "th-group-condition",
                "th-group-condition",
                "th-group-condition",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment",
                "th-group-experiment"
            ];

            visibleHeader.each(function(index) {
                $(this).removeClass('th-group-record th-group-condition th-group-experiment');
                $(this).addClass(groupClasses[index]);
            });

            $(visibleHeader[0]).addClass('no-sort');

            applyHeaderTooltips(api);
        }
    });
}

async function refreshExplore() {
    const scrollY = window.scrollY;
    updateUrlFromSelections();
    await loadInfoPanels();
    await loadHistogram();
    await loadRanking();
    await loadDoseResponse();
    await loadTable();
    window.scrollTo({
        top: scrollY,
        behavior: "auto"
    });
}

document.getElementById("organism-select").addEventListener("change", async function() {
    exploreTableShowAll = false;
    document.getElementById("category-select").value = "";
    document.getElementById("endpoint-select").value = "";
    document.getElementById("chemical-select").value = "";
    await loadOptions();
    await refreshExplore();
});

document.getElementById("category-select").addEventListener("change", async function() {
    exploreTableShowAll = false;
    document.getElementById("endpoint-select").value = "";
    await loadOptions();
    await refreshExplore();
});

document.getElementById("endpoint-select").addEventListener("change", async function() {
    exploreTableShowAll = false;
    document.getElementById("chemical-select").value = "";
    await loadOptions();
    await refreshExplore();
});

document.getElementById("chemical-select").addEventListener("change", async function() {
    exploreTableShowAll = false;
    await refreshExplore();
});

document.getElementById("ranking-mode-select").addEventListener("change", async function() {
    updateUrlFromSelections();
    await loadRanking();
});

document.getElementById("show-all-table-btn").addEventListener("click", async function() {
    exploreTableShowAll = true;
    await loadTable();
});

document.getElementById("dose-log-scale").addEventListener("change", async function() {
    await loadDoseResponse();
});

const initialSelections = applySelectionsFromUrl();

Plotly.newPlot("histogram", [], {
    title: {
        text: "Select organism, endpoint category and endpoint",
        font: {
            size: 14
        }
    },
    xaxis: { visible: false },
    yaxis: { visible: false }
}, { responsive: true });

Plotly.newPlot("ranking-plot", [], {
    title: {
        text: "Select organism, endpoint category and endpoint",
        font: {
            size: 14
        }
    },
    xaxis: { visible: false },
    yaxis: { visible: false }
}, { responsive: true });

document.getElementById("dose-response-container").innerHTML =
    '<div id="dose-response-empty" class="chart-box chart-box-placeholder"></div>';

Plotly.newPlot("dose-response-empty", [], {
    title: {
        text: "Select organism, endpoint category, endpoint and chemical",
        font: {
            size: 14
        }
    },
    xaxis: { visible: false },
    yaxis: { visible: false }
}, { responsive: true });

(async function initExploreFromUrl() {
    if (document.getElementById("organism-select").value) {
        await loadOptions();

        if (initialSelections.effect_type) {
            document.getElementById("category-select").value = initialSelections.effect_type;
            await loadOptions();
        }

        if (initialSelections.endpoint_name) {
            document.getElementById("endpoint-select").value = initialSelections.endpoint_name;
            await loadOptions();
        }

        if (initialSelections.ptx_code) {
            document.getElementById("chemical-select").value = initialSelections.ptx_code;
        }

        await refreshExplore();
    } else {
        loadInfoPanels();
    }
})();
