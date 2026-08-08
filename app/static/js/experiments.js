function applyHeaderTooltips(api) {
    const tableElement = document.getElementById("experiments-table");
    const columnDescriptions = JSON.parse(tableElement.dataset.columnDescriptions || "{}");
    const visibleHeader = $(api.table().container()).find('.dataTables_scrollHead thead tr:first-child th');

    visibleHeader.each(function() {
        const headerText = $(this).text().trim();
        if (columnDescriptions[headerText]) {
            $(this).attr('title', columnDescriptions[headerText]);
        }
    });
}

$(document).ready(function() {
    var table = $('#experiments-table').DataTable({
        pageLength: 25,
        lengthMenu: [10, 25, 50, 100],
        order: [[4, 'desc']],
        autoWidth: false,
        scrollX: true,
        dom: 'Bfrtip',
        orderCellsTop: true,
        buttons: [
            {
                extend: 'csvHtml5',
                text: 'Export CSV',
                title: 'precisiontox_experiments',
                exportOptions: { columns: ':visible' }
            }
        ],
        columnDefs: [
            { orderable: false, targets: 0 },
            { className: "dt-right", targets: [10,11,12,13,15,16] },
            { visible: false, targets: [16,17,18] }
        ],
        initComplete: function () {
            var api = this.api();

            // Visible header when scrollX is enabled
            var visibleHeader = $(api.table().container()).find('.dataTables_scrollHead thead');

            // Prevent sorting when interacting with filter row
            visibleHeader.find('tr:eq(1) th').on('click', function(e) {
                e.stopPropagation();
            });

            visibleHeader.find('tr:eq(1) th input').on('click focus', function(e) {
                e.stopPropagation();
            });

            // Column filters
            visibleHeader.find('tr:eq(1) th input').on('keyup change', function(e) {
                e.stopPropagation();
                let colIndex = $(this).closest('th').index();
                api.column(colIndex).search(this.value).draw();
            });

            // Apply tooltip descriptions
            applyHeaderTooltips(api);
        }
    });
    table.on('draw', function() {
        updateSummaryCards(table);
    });
});

function updateSummaryCards(api) {
    let nExperiments = 0;
    let nConditions = 0;
    let nRecords = 0;
    let organisms = new Set();
    let chemicals = new Set();
    let endpoints = new Set();

    api.rows({ search: 'applied' }).every(function() {
        const row = this.data();

        nExperiments += 1;
        organisms.add(row[2]);               // Organism
        nConditions += Number(row[10]) || 0; // # Conditions
        nRecords += Number(row[15]) || 0;    // # Records

        const chemicalKeys = row[17] || "";
        const endpointKeys = row[18] || "";

        if (chemicalKeys) {
            chemicalKeys.split("||").forEach(x => {
                if (x) chemicals.add(x);
            });
        }

        if (endpointKeys) {
            endpointKeys.split("||").forEach(x => {
                if (x) endpoints.add(x);
            });
        }
    });

    document.getElementById('card-n-experiments').textContent = nExperiments;
    document.getElementById('card-n-conditions').textContent = nConditions;
    document.getElementById('card-n-records').textContent = nRecords;
    document.getElementById('card-n-endpoints').textContent = endpoints.size;
    document.getElementById('card-n-organisms').textContent = organisms.size;
    document.getElementById('card-n-chemicals').textContent = chemicals.size;
}
