let compareTable = null;
let compareTableShowAll = false;
let activeCompareTab = "heatmap";
let appliedEndpointNames = [];

function getSelectedEndpointNames() {
    const endpointSelect = document.getElementById("compare-endpoint-select");
    return [...endpointSelect.selectedOptions]
        .map(option => option.value)
        .filter(Boolean);
}

function clearSelectedEndpoints() {
    [...document.getElementById("compare-endpoint-select").options].forEach(option => {
        option.selected = false;
    });
}

function setSelectedEndpointNames(endpointNames) {
    const selectedNames = new Set(endpointNames.filter(Boolean));
    [...document.getElementById("compare-endpoint-select").options].forEach(option => {
        option.selected = selectedNames.has(option.value);
    });
}

function appendEndpointParams(params, endpointNames) {
    endpointNames.forEach(endpointName => params.append("endpoint_name", endpointName));
}

function endpointSelectionsMatch(a, b) {
    if (a.length !== b.length) return false;
    const bSet = new Set(b);
    return a.every(endpointName => bSet.has(endpointName));
}

function updateEndpointApplyButton() {
    const button = document.getElementById("compare-apply-endpoints-btn");
    const selectedEndpointNames = getSelectedEndpointNames();
    const hasPendingChange = !endpointSelectionsMatch(selectedEndpointNames, appliedEndpointNames);
    button.hidden = !hasPendingChange;
    button.disabled = !hasPendingChange;
}

function renderEndpointChips() {
    const selectionBox = document.getElementById("compare-endpoint-selection");
    const chipList = document.getElementById("compare-endpoint-chips");
    const countLabel = document.getElementById("compare-endpoint-selection-count");
    const endpointSelect = document.getElementById("compare-endpoint-select");

    const selectedOptions = [...endpointSelect.selectedOptions].filter(option => option.value);

    if (!selectedOptions.length) {
        selectionBox.hidden = true;
        chipList.replaceChildren();
        return;
    }

    selectionBox.hidden = false;
    countLabel.textContent = `${selectedOptions.length} endpoint${selectedOptions.length === 1 ? "" : "s"} selected`;

    chipList.replaceChildren(...selectedOptions.map(option => {
        const label = option.textContent.trim();

        const chip = document.createElement("li");
        chip.className = "endpoint-chip";

        const chipLabel = document.createElement("span");
        chipLabel.className = "endpoint-chip-label";
        chipLabel.textContent = label;
        chipLabel.title = label;

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "endpoint-chip-remove";
        removeButton.dataset.endpointName = option.value;
        removeButton.setAttribute("aria-label", `Remove ${label}`);
        removeButton.textContent = "×";

        chip.append(chipLabel, removeButton);
        return chip;
    }));
}

function updateEndpointSelectionUi() {
    updateEndpointApplyButton();
    renderEndpointChips();
}

function setCompareTab(tabName) {
    activeCompareTab = tabName;

    document.querySelectorAll(".compare-tab").forEach(button => {
        const isActive = button.dataset.tab === tabName;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    document.querySelectorAll(".compare-tab-panel").forEach(panel => {
        const isActive = panel.id === `compare-panel-${tabName}`;
        panel.classList.toggle("active", isActive);
        panel.hidden = !isActive;
    });

    if (tabName === "heatmap") {
        Plotly.Plots.resize(document.getElementById("compare-heatmap"));
    } else if (tabName === "pca") {
        Plotly.Plots.resize(document.getElementById("compare-pca"));
    } else if (compareTable) {
        compareTable.columns.adjust();
    }
}

function compareSelections() {
    return {
        organism_id: document.getElementById("compare-organism-select").value,
        effect_type: document.getElementById("compare-category-select").value,
        endpoint_name: appliedEndpointNames[0] || "",
        endpoint_names: appliedEndpointNames,
        metric: document.getElementById("compare-metric-select").value,
        clustering: document.getElementById("compare-clustering-select").value,
        toxicity_category: document.getElementById("compare-toxicity-category-select").value,
        rr_group: document.getElementById("compare-rr-group-select").value
    };
}

function updateCompareMetricNote() {
    const metric = document.getElementById("compare-metric-select").value;
    const note = document.getElementById("compare-metric-note");
    if (metric === "zscore") {
        note.textContent = "Z-score colors are centered on 0, with values from -1 to +1 shown in grey as a non-significant range.";
    } else {
        note.textContent = "Heatmap colors are normalized by endpoint so endpoints with different units and scales can be compared visually.";
    }
}

function updateCompareUrl() {
    const { organism_id, effect_type, endpoint_names, metric, clustering, toxicity_category, rr_group } = compareSelections();
    const params = new URLSearchParams();
    if (organism_id) params.set("organism_id", organism_id);
    if (effect_type) params.set("effect_type", effect_type);
    appendEndpointParams(params, endpoint_names);
    if (metric) params.set("metric", metric);
    if (clustering) params.set("clustering", clustering);
    if (toxicity_category) params.set("toxicity_category", toxicity_category);
    if (rr_group) params.set("rr_group", rr_group);
    window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
}

function applyCompareSelectionsFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const organism_id = params.get("organism_id") || "";
    const effect_type = params.get("effect_type") || "";
    const endpoint_names = params.getAll("endpoint_name").filter(Boolean);
    const metric = params.get("metric") || "difference";
    const clustering = params.get("clustering") || "default";
    const toxicity_category = params.get("toxicity_category") || "";
    const rr_group = params.get("rr_group") || "";

    document.getElementById("compare-organism-select").value = organism_id;
    document.getElementById("compare-metric-select").value = metric;
    document.getElementById("compare-clustering-select").value = clustering;

    return { effect_type, endpoint_names, toxicity_category, rr_group };
}

function getSelections() {
    return {
        organism_id: document.getElementById("compare-organism-select").value,
        effect_type: document.getElementById("compare-category-select").value,
        endpoint_name: appliedEndpointNames[0] || "",
        endpoint_names: appliedEndpointNames,
    };
}

async function loadCompareOptions() {
    const organism_id = document.getElementById("compare-organism-select").value;
    const currentCategory = document.getElementById("compare-category-select").value;
    const currentEndpoints = getSelectedEndpointNames();
    const categorySelect = document.getElementById("compare-category-select");
    const endpointSelect = document.getElementById("compare-endpoint-select");

    if (!organism_id) {
        categorySelect.innerHTML = '<option value="">All endpoint categories</option>';
        endpointSelect.innerHTML = '<option value="">All endpoints</option>';
        categorySelect.disabled = true;
        endpointSelect.disabled = true;
        updateEndpointSelectionUi();
        return;
    }

    categorySelect.disabled = true;
    endpointSelect.disabled = true;

    const params = new URLSearchParams({ organism_id });
    if (currentCategory) params.append("effect_type", currentCategory);

    const response = await fetch(`${window.APP_ROOT}/api/compare/options?${params.toString()}`);
    const data = await response.json();

    categorySelect.innerHTML =
        '<option value="">All endpoint categories</option>' +
        data.categories.map(x => `<option value="${x.effect_type}">${x.effect_type}</option>`).join("");

    endpointSelect.innerHTML =
        '<option value="">All endpoints</option>' +
        data.endpoints.map(x => `<option value="${x.endpoint_name}">${x.endpoint_display_name}</option>`).join("");

    categorySelect.disabled = false;
    endpointSelect.disabled = false;

    if ([...categorySelect.options].some(opt => opt.value === currentCategory)) {
        categorySelect.value = currentCategory;
    }

    setSelectedEndpointNames(currentEndpoints);
    updateEndpointSelectionUi();
}

async function loadToxicityCategories(selectedCategory = "") {
    const organism_id = document.getElementById("compare-organism-select").value;
    const toxicitySelect = document.getElementById("compare-toxicity-category-select");

    if (!organism_id) {
        toxicitySelect.innerHTML = '<option value="">All toxicity categories</option>';
        toxicitySelect.disabled = true;
        return;
    }

    const response = await fetch(`${window.APP_ROOT}/api/compare/toxicity-categories?${new URLSearchParams({ organism_id }).toString()}`);
    const data = await response.json();
    toxicitySelect.replaceChildren(new Option("All toxicity categories", ""));
    data.categories.forEach(x => {
        toxicitySelect.add(new Option(`${x.tox_class} (${x.n_chemicals})`, x.tox_class));
    });

    toxicitySelect.disabled = false;
    if ([...toxicitySelect.options].some(opt => opt.value === selectedCategory)) {
        toxicitySelect.value = selectedCategory;
    } else {
        toxicitySelect.value = "";
    }
}

async function loadRrGroups(selectedGroup = "") {
    const organism_id = document.getElementById("compare-organism-select").value;
    const rrGroupSelect = document.getElementById("compare-rr-group-select");

    if (!organism_id) {
        rrGroupSelect.innerHTML = '<option value="">All chemical groups</option>';
        rrGroupSelect.disabled = true;
        return;
    }

    const response = await fetch(`${window.APP_ROOT}/api/compare/rr-groups?${new URLSearchParams({ organism_id }).toString()}`);
    const data = await response.json();
    rrGroupSelect.replaceChildren(new Option("All chemical groups", ""));
    data.groups.forEach(x => {
        rrGroupSelect.add(new Option(`${x.group_name} (${x.n_chemicals})`, x.group_name));
    });

    rrGroupSelect.disabled = false;
    if ([...rrGroupSelect.options].some(opt => opt.value === selectedGroup)) {
        rrGroupSelect.value = selectedGroup;
    } else {
        rrGroupSelect.value = "";
    }
}

async function loadInfoPanels() {
    const { organism_id, effect_type, endpoint_name, endpoint_names } = getSelections();

    const organismBox = document.getElementById("organism-info");
    const categoryBox = document.getElementById("category-info");
    const endpointCard = document.getElementById("endpoint-info-card");
    const endpointBox = document.getElementById("endpoint-info");

    if (!organism_id) {
        organismBox.innerHTML = '<span class="text-muted">Select an organism.</span>';
        categoryBox.innerHTML = '<span class="text-muted">Select an endpoint category.</span>';
        endpointBox.innerHTML = '<span class="text-muted">Select an endpoint.</span>';
        endpointCard.hidden = true;
        return;
    }

    const params = new URLSearchParams({ organism_id });
    if (effect_type) params.append("effect_type", effect_type);
    if (endpoint_names.length === 1) params.append("endpoint_name", endpoint_name);

    const response = await fetch(`${window.APP_ROOT}/api/explore/info?${params.toString()}`);
    const data = await response.json();

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

    if (endpoint_names.length > 1) {
        endpointCard.hidden = false;
        endpointBox.innerHTML = `
            <div class="info-row"><span class="info-label">Selected endpoints:</span><strong> ${endpoint_names.length}</strong></div>
        `;
    } else if (endpoint_names.length === 1 && data.endpoint) {
        endpointCard.hidden = false;
        endpointBox.innerHTML = `
            <div class="info-row"><span class="info-label">Display name:</span><strong> ${data.endpoint.display_name || ""}</strong></div>
            <div class="info-row"><span class="info-label">Original name:</span> ${data.endpoint.name || ""}</div>
            <div class="info-row"><span class="info-label">Ontology term:</span> ${data.endpoint.ontology_term || ""}</div>
            <div class="info-row"><span class="info-label">Description:</span> ${data.endpoint.description || ""}</div>
            <div class="info-row"><span class="info-label">Unit:</span> ${data.endpoint.unit || ""}</div>
            <div class="info-row"><span class="info-label">Data type:</span> ${data.endpoint.data_type || ""}</div>
        `;
    } else {
        endpointBox.innerHTML = '<span class="text-muted">Select an endpoint.</span>';
        endpointCard.hidden = true;
    }
}

function clearComparePca(title) {
    Plotly.newPlot("compare-pca", [], {
        title,
        xaxis: { visible: false },
        yaxis: { visible: false }
    }, { responsive: true });
}

function normalizeHeatmapColumns(z) {
    const displayZ = z.map(row => row.slice());
    const nRows = displayZ.length;
    const nCols = displayZ[0]?.length || 0;

    for (let j = 0; j < nCols; j++) {
        const vals = [];
        for (let i = 0; i < nRows; i++) {
            const v = displayZ[i][j];
            if (v !== null && !Number.isNaN(v)) {
                vals.push(v);
            }
        }

        if (vals.length === 0) continue;

        const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
        const variance = vals.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / vals.length;
        const sd = Math.sqrt(variance);

        for (let i = 0; i < nRows; i++) {
            const v = displayZ[i][j];
            if (v === null || Number.isNaN(v)) {
                displayZ[i][j] = null;
            } else if (sd === 0) {
                displayZ[i][j] = 0;
            } else {
                displayZ[i][j] = (v - mean) / sd;
            }
        }
    }

    return displayZ;
}

function maxAbsHeatmapValue(z) {
    let maxAbs = 0;
    z.forEach(row => {
        row.forEach(value => {
            if (value !== null && !Number.isNaN(value)) {
                maxAbs = Math.max(maxAbs, Math.abs(value));
            }
        });
    });
    return maxAbs;
}

function zScoreHeatmapColorConfig(z) {
    const limit = Math.max(1, maxAbsHeatmapValue(z));
    const grey = "#d9d9d9";

    if (limit <= 1) {
        return {
            zmin: -1,
            zmax: 1,
            colorscale: [[0, grey], [1, grey]],
            colorbar: { title: "Z-score" }
        };
    }

    const negativeThreshold = (limit - 1) / (2 * limit);
    const positiveThreshold = (limit + 1) / (2 * limit);
    const edge = 0.0001;
    const negativeMidpoint = negativeThreshold / 2;
    const positiveMidpoint = positiveThreshold + (1 - positiveThreshold) / 2;

    return {
        zmin: -limit,
        zmax: limit,
        colorscale: [
            [0, "#2166ac"],
            [negativeMidpoint, "#67a9cf"],
            [Math.max(0, negativeThreshold - edge), "#c9dce8"],
            [negativeThreshold, grey],
            [positiveThreshold, grey],
            [Math.min(1, positiveThreshold + edge), "#edc8bf"],
            [positiveMidpoint, "#ef8a62"],
            [1, "#b2182b"]
        ],
        colorbar: {
            title: "Z-score",
            tickmode: "array",
            tickvals: [-limit, -1, 0, 1, limit],
            ticktext: [
                (-limit).toFixed(2),
                "-1",
                "0",
                "1",
                limit.toFixed(2)
            ]
        }
    };
}

function firstEigenpair(matrix, blockedVector = null) {
    const n = matrix.length;
    let vector = Array.from({ length: n }, (_, i) => (blockedVector ? i + 1 : 1));

    if (blockedVector) {
        const projection = vector.reduce((acc, v, i) => acc + v * blockedVector[i], 0);
        vector = vector.map((v, i) => v - projection * blockedVector[i]);
    }
    const initialNorm = Math.sqrt(vector.reduce((acc, v) => acc + v * v, 0));
    vector = initialNorm ? vector.map(v => v / initialNorm) : Array.from({ length: n }, () => 0);

    for (let iter = 0; iter < 80; iter++) {
        let next = matrix.map(row => row.reduce((acc, v, i) => acc + v * vector[i], 0));
        if (blockedVector) {
            const projection = next.reduce((acc, v, i) => acc + v * blockedVector[i], 0);
            next = next.map((v, i) => v - projection * blockedVector[i]);
        }
        const norm = Math.sqrt(next.reduce((acc, v) => acc + v * v, 0));
        if (norm === 0) break;
        vector = next.map(v => v / norm);
    }

    const multiplied = matrix.map(row => row.reduce((acc, v, i) => acc + v * vector[i], 0));
    const value = vector.reduce((acc, v, i) => acc + v * multiplied[i], 0);
    return { value, vector };
}

function renderComparePca(data, displayZ) {
    if (!data.x.length || !data.y.length) {
        clearComparePca("No data available for PCA");
        return;
    }

    if (data.x.length < 2 || data.y.length < 2) {
        clearComparePca("PCA needs at least two endpoints and two chemicals");
        return;
    }

    const matrix = displayZ.map(row => row.map(v => (v === null || Number.isNaN(v)) ? 0 : v));
    const nRows = matrix.length;
    const nCols = matrix[0].length;
    const colMeans = Array.from({ length: nCols }, (_, j) =>
        matrix.reduce((acc, row) => acc + row[j], 0) / nRows
    );
    const centered = matrix.map(row => row.map((v, j) => v - colMeans[j]));
    const covariance = Array.from({ length: nCols }, (_, a) =>
        Array.from({ length: nCols }, (_, b) =>
            centered.reduce((acc, row) => acc + row[a] * row[b], 0) / Math.max(1, nRows - 1)
        )
    );

    const pc1 = firstEigenpair(covariance);
    const pc2 = firstEigenpair(covariance, pc1.vector);
    const totalVariance = covariance.reduce((acc, row, i) => acc + row[i], 0);
    const pc1Pct = totalVariance > 0 ? Math.max(0, pc1.value) / totalVariance * 100 : 0;
    const pc2Pct = totalVariance > 0 ? Math.max(0, pc2.value) / totalVariance * 100 : 0;
    const scores = centered.map(row => [
        row.reduce((acc, v, j) => acc + v * pc1.vector[j], 0),
        row.reduce((acc, v, j) => acc + v * pc2.vector[j], 0)
    ]);

    Plotly.newPlot("compare-pca", [{
        x: scores.map(row => row[0]),
        y: scores.map(row => row[1]),
        text: data.y,
        customdata: data.y,
        type: "scatter",
        mode: "markers",
        marker: {
            size: 9,
            color: scores.map(row => row[0]),
            colorscale: "Viridis",
            showscale: false,
            line: { color: "#ffffff", width: 0.7 }
        },
        hovertemplate:
            "Chemical: %{customdata}<br>" +
            "PC1: %{x:.3f}<br>" +
            "PC2: %{y:.3f}<extra></extra>"
    }], {
        title: "PCA of current heatmap values",
        height: 720,
        xaxis: { title: `PC1 (${pc1Pct.toFixed(1)}%)`, zeroline: true },
        yaxis: { title: `PC2 (${pc2Pct.toFixed(1)}%)`, zeroline: true },
        margin: { l: 70, r: 30, t: 60, b: 70 }
    }, { responsive: true });
}

async function loadCompareHeatmap() {
    const { organism_id, effect_type, endpoint_names, metric, clustering, toxicity_category, rr_group } = compareSelections();
    updateCompareMetricNote();

    if (!organism_id) {
        Plotly.newPlot("compare-heatmap", [], {
            title: "Select an organism",
            xaxis: { visible: false },
            yaxis: { visible: false }
        }, { responsive: true });
        clearComparePca("Select an organism");
        return;
    }

    const params = new URLSearchParams({ organism_id, metric, clustering });
    if (effect_type) params.append("effect_type", effect_type);
    appendEndpointParams(params, endpoint_names);
    if (toxicity_category) params.append("toxicity_category", toxicity_category);
    if (rr_group) params.append("rr_group", rr_group);

    const response = await fetch(`${window.APP_ROOT}/api/compare/heatmap?${params.toString()}`);

    if (!response.ok) {
        const text = await response.text();
        console.error("Compare heatmap error:", response.status, text);
        throw new Error(`Compare heatmap request failed: ${response.status}`);
    }

    const data = await response.json();

    if (!data.x.length || !data.y.length) {
        Plotly.newPlot("compare-heatmap", [], {
            title: "No data available for the selected filters",
            xaxis: { visible: false },
            yaxis: { visible: false }
        }, { responsive: true });
        clearComparePca("No data available for the selected filters");
        return;
    }

    const yPositions = data.y.map((_, i) => i);

    // Keep the raw values for hover
    const rawZ = data.z.map(row => row.slice());

    const usesZScoreColorScale = data.metric === "zscore";
    const displayZ = usesZScoreColorScale
        ? data.z.map(row => row.slice())
        : normalizeHeatmapColumns(data.z);
    renderComparePca(data, displayZ);

    const titleMap = {
        difference: "Chemical comparison heatmap — Difference",
        zscore: "Chemical comparison heatmap — Z-score",
        response_score: "Chemical comparison heatmap — Dose-response evidence"
    };

    // Dynamic height so all chemicals are actually visible
    const dynamicHeight = Math.max(900, data.y.length * 18);

    const dendrogramX = [];
    const dendrogramY = [];
    (data.dendrogram || []).forEach(segment => {
        dendrogramX.push(...segment.x, null);
        dendrogramY.push(...segment.y, null);
    });

    const hasDendrogram = dendrogramX.length > 0;
    const traces = [];
    if (hasDendrogram) {
        traces.push({
            x: dendrogramX,
            y: dendrogramY,
            type: "scatter",
            mode: "lines",
            line: { color: "#415a70", width: 1.2 },
            hoverinfo: "skip",
            showlegend: false,
            xaxis: "x",
            yaxis: "y"
        });
    }

    const colorConfig = usesZScoreColorScale
        ? zScoreHeatmapColorConfig(displayZ)
        : {
            colorscale: "RdBu",
            reversescale: true,
            zmid: 0,
            colorbar: { title: "Endpoint-normalized value" }
        };

    traces.push({
        z: displayZ,
        x: data.x,
        y: yPositions,
        customdata: rawZ.map((row, i) =>
            row.map((rawVal, j) => [
                data.y[i],
                rawVal,
                data.customdata[i][j][0],  // n_experiments
                data.customdata[i][j][1],  // n_with_control
                data.customdata[i][j][2]   // n_without_control
            ])
        ),
        type: "heatmap",
        ...colorConfig,
        xaxis: "x2",
        yaxis: "y",
        hoverongaps: false,
        hovertemplate:
            "Chemical: %{customdata[0]}<br>" +
            "Endpoint: %{x}<br>" +
            "Raw value: %{customdata[1]}<br>" +
            "Displayed color value: %{z}<br>" +
            "Experiments: %{customdata[2]}<br>" +
            "With controls: %{customdata[3]}<br>" +
            "Without controls: %{customdata[4]}<extra></extra>"
    });

    Plotly.newPlot("compare-heatmap", traces, {
        title: (titleMap[data.metric] || "Chemical comparison heatmap") +
            (usesZScoreColorScale ? " (grey = -1 to +1)" : " (endpoint-normalized colors)"),
        height: dynamicHeight,
        xaxis: {
            domain: hasDendrogram ? [0, 0.13] : [0, 0],
            autorange: "reversed",
            showgrid: false,
            zeroline: false,
            showticklabels: false,
            visible: hasDendrogram
        },
        xaxis2: {
            domain: hasDendrogram ? [0.17, 1] : [0, 1],
            title: "Endpoint",
            automargin: true,
            tickangle: -60,
            tickfont: { size: 10 }
        },
        yaxis: {
            title: "Chemical",
            automargin: true,
            tickmode: "array",
            tickvals: yPositions,
            ticktext: data.y,
            tickfont: { size: 10 },
            range: [data.y.length - 0.5, -0.5]
        },
        margin: { l: 260, r: 30, t: 60, b: 260 }
    }, { responsive: true });
}

async function loadCompareTable() {
    const { organism_id, effect_type, endpoint_names } = compareSelections();

    if (!organism_id) {
        if (compareTable) {
            compareTable.destroy();
            compareTable = null;
        }
        $('#compare-table tbody').empty();
        document.getElementById("compare-table-note").textContent = "";
        document.getElementById("compare-show-all-table-btn").style.display = "none";
        return;
    }

    const params = new URLSearchParams({ organism_id });
    if (effect_type) params.append("effect_type", effect_type);
    appendEndpointParams(params, endpoint_names);
    if (compareTableShowAll) params.append("show_all", "1");

    const response = await fetch(`${window.APP_ROOT}/api/compare/table?${params.toString()}`);

    if (!response.ok) {
        const text = await response.text();
        console.error("Compare heatmap error:", response.status, text);
        throw new Error(`Compare heatmap request failed: ${response.status}`);
    }

    const data = await response.json();

    const rows = data.rows.map(r => [
        r.phenotype_record_id,
        r.endpoint_category || "",
        r.endpoint_display_name || r.endpoint_name || "",
        r.effect_value || "",
        r.endpoint_unit || "",
        r.is_control,
        r.sample_type || "",
        r.full_ptx_code ? `[${r.full_ptx_code}] ${r.chemical_name}` : "",
        r.exposure_concentration !== null
            ? `${r.exposure_concentration} ${r.exposure_concentration_unit || ""}`.trim()
            : "",
        r.exposure_duration !== null
            ? `${r.exposure_duration} ${r.exposure_duration_unit || ""}`.trim()
            : "",
        r.internal_experiment_batch_id || "",
        r.partner_id || "",
        r.experiment_date || "",
        r.biosystem_code || "",
        r.organism || "",
        r.medium || "",
        r.format_exposure || "",
        r.aggregated_data,
        r.quality_flag || ""
    ]);

    const note = document.getElementById("compare-table-note");
    const showAllBtn = document.getElementById("compare-show-all-table-btn");

    if (data.is_truncated) {
        note.textContent = "Showing first 5000 records. Click 'Show everything' to load all matching rows.";
        showAllBtn.style.display = "inline-block";
    } else {
        note.textContent = compareTableShowAll ? "Showing all matching records." : "";
        showAllBtn.style.display = "none";
    }

    if (compareTable) {
        compareTable.destroy();
        compareTable = null;
    }

    $('#compare-table tbody').empty();

    compareTable = $('#compare-table').DataTable({
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
                title: 'precisiontox_compare_records'
            }
        ],
        columnDefs: [
            { orderable: false, targets: 0, className: "no-sort" }
        ]
    });
}

async function refreshCompare() {
    updateCompareUrl();
    await loadInfoPanels();
    await loadCompareHeatmap();
    await loadCompareTable();
}

document.getElementById("compare-organism-select").addEventListener("change", async function() {
    compareTableShowAll = false;
    document.getElementById("compare-category-select").value = "";
    clearSelectedEndpoints();
    appliedEndpointNames = [];
    updateEndpointSelectionUi();
    document.getElementById("compare-toxicity-category-select").value = "";
    document.getElementById("compare-rr-group-select").value = "";
    await loadCompareOptions();
    await loadToxicityCategories();
    await loadRrGroups();
    await refreshCompare();
});

document.getElementById("compare-category-select").addEventListener("change", async function() {
    compareTableShowAll = false;
    clearSelectedEndpoints();
    appliedEndpointNames = [];
    updateEndpointSelectionUi();
    await loadCompareOptions();
    await refreshCompare();
});

document.getElementById("compare-endpoint-select").addEventListener("change", function() {
    compareTableShowAll = false;
    updateEndpointSelectionUi();
});

// Plain click toggles an endpoint instead of replacing the whole selection, so
// building a multi-endpoint selection does not require Ctrl/Cmd+click.
document.getElementById("compare-endpoint-select").addEventListener("mousedown", function(event) {
    const option = event.target.closest("option");
    if (!option || option.disabled) return;

    event.preventDefault();

    if (option.value) {
        option.selected = !option.selected;
        // "All endpoints" is a reset, so it never stays selected alongside specific endpoints.
        [...this.options].forEach(candidate => {
            if (!candidate.value) candidate.selected = false;
        });
    } else {
        clearSelectedEndpoints();
    }

    this.focus();
    this.dispatchEvent(new Event("change", { bubbles: true }));
});

document.getElementById("compare-endpoint-chips").addEventListener("click", function(event) {
    const removeButton = event.target.closest(".endpoint-chip-remove");
    if (!removeButton) return;

    const endpointSelect = document.getElementById("compare-endpoint-select");
    const option = [...endpointSelect.options].find(candidate => candidate.value === removeButton.dataset.endpointName);
    if (!option) return;

    option.selected = false;
    endpointSelect.dispatchEvent(new Event("change", { bubbles: true }));
});

document.getElementById("compare-clear-endpoints-btn").addEventListener("click", function() {
    const endpointSelect = document.getElementById("compare-endpoint-select");
    clearSelectedEndpoints();
    endpointSelect.dispatchEvent(new Event("change", { bubbles: true }));
});

document.getElementById("compare-apply-endpoints-btn").addEventListener("click", async function() {
    compareTableShowAll = false;
    appliedEndpointNames = getSelectedEndpointNames();
    updateEndpointSelectionUi();
    await refreshCompare();
});

document.getElementById("compare-metric-select").addEventListener("change", async function() {
    await loadCompareHeatmap();
    updateCompareUrl();
});

document.getElementById("compare-clustering-select").addEventListener("change", async function() {
    await loadCompareHeatmap();
    updateCompareUrl();
});

document.getElementById("compare-toxicity-category-select").addEventListener("change", async function() {
    await loadCompareHeatmap();
    updateCompareUrl();
});

document.getElementById("compare-rr-group-select").addEventListener("change", async function() {
    await loadCompareHeatmap();
    updateCompareUrl();
});

document.getElementById("compare-show-all-table-btn").addEventListener("click", async function() {
    compareTableShowAll = true;
    await loadCompareTable();
});

document.querySelectorAll(".compare-tab").forEach(button => {
    button.addEventListener("click", function() {
        setCompareTab(this.dataset.tab);
    });
});

const initialCompareSelections = applyCompareSelectionsFromUrl();

Plotly.newPlot("compare-heatmap", [], {
    title: "Select an organism",
    xaxis: { visible: false },
    yaxis: { visible: false }
}, { responsive: true });

(async function initCompareFromUrl() {
    if (document.getElementById("compare-organism-select").value) {
        await loadCompareOptions();
        await loadToxicityCategories(initialCompareSelections.toxicity_category);
        await loadRrGroups(initialCompareSelections.rr_group);

        if (initialCompareSelections.effect_type) {
            document.getElementById("compare-category-select").value = initialCompareSelections.effect_type;
            await loadCompareOptions();
        }

        setSelectedEndpointNames(initialCompareSelections.endpoint_names);
        appliedEndpointNames = initialCompareSelections.endpoint_names.slice();
        updateEndpointSelectionUi();

        await refreshCompare();
    }
})();
