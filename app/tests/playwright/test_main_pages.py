import os

import pytest
from playwright.sync_api import expect


BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


def heatmap_state(page):
    return page.locator("#compare-heatmap").evaluate(
        """el => {
            if (!el.data || !el.layout) return null;

            return {
                dataRevision: el.layout.datarevision || null,
                title: el.layout.title?.text || null,
                xLength: el.data[0]?.x?.length || 0,
                yLength: el.data[0]?.y?.length || 0,
                zSample: JSON.stringify(el.data[0]?.z || []).slice(0, 500),
            };
        }"""
    )


def wait_for_heatmap_state_change(page, previous_state):
    page.wait_for_function(
        """previous => {
            const el = document.querySelector("#compare-heatmap");
            if (!el || !el.data || !el.layout) return false;

            const current = {
                title: el.layout.title?.text || null,
                xLength: el.data[0]?.x?.length || 0,
                yLength: el.data[0]?.y?.length || 0,
                zSample: JSON.stringify(el.data[0]?.z || []).slice(0, 500),
            };

            return JSON.stringify(current) !== JSON.stringify(previous);
        }""",
        arg=previous_state,
        timeout=10_000,
    )

@pytest.mark.parametrize(
    ("path", "heading"),
    [
        ("/", "PrecisionTox phenotype dashboard"),
        ("/explore/", "Explore Endpoints"),
        ("/compare/", "Compare Endpoints"),
        ("/experiments/", "Experiment Information"),
    ],
)

def test_main_pages_render(page, path, heading):
    page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded")

    expect(page).to_have_title("PrecisionTox Phenotype")
    expect(page.get_by_role("heading", name=heading)).to_be_visible()


def test_navbar(page):
    page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
 
    page.get_by_role("link", name="Explore", exact=True).click()
    expect(page).to_have_url(f"{BASE_URL}/explore/")
    expect(page.get_by_role("heading", name="Explore Endpoints")).to_be_visible()

    page.get_by_role("link", name="Compare", exact=True).click()
    expect(page).to_have_url(f"{BASE_URL}/compare/")
    expect(page.get_by_role("heading", name="Compare Endpoints")).to_be_visible()

    page.get_by_role("link", name="Experiments", exact=True).click()
    expect(page).to_have_url(f"{BASE_URL}/experiments/")
    expect(page.get_by_role("heading", name="Experiment Information")).to_be_visible()

    page.get_by_role("link", name="Home", exact=True).click()
    expect(page).to_have_url(f"{BASE_URL}/")
    expect(page.get_by_role("heading", name="PrecisionTox phenotype dashboard")).to_be_visible()


def test_explore_options_selectors(page):
    # Go to "Explore" page
    page.goto(f"{BASE_URL}/explore/", wait_until="domcontentloaded")

    # Find dropdown option selectors 
    organism_select = page.locator("#organism-select")
    category_select = page.locator("#category-select")
    endpoint_select = page.locator("#endpoint-select")
    chemical_select = page.locator("#chemical-select")

    # Check default dropdowns statuses
    expect(organism_select).to_be_enabled()
    expect(category_select).to_be_disabled()
    expect(endpoint_select).to_be_disabled()
    expect(chemical_select).to_be_disabled()

    # Check organisms options, select first
    organism_count = organism_select.locator("option").count()
    assert organism_count > 1
    organism_select.select_option(index=1)

    # Check status change, select first option
    expect(category_select).to_be_enabled()
    category_select.select_option(index=1)
    
    # Check status change, select first option
    expect(endpoint_select).to_be_enabled()
    endpoint_select.select_option(index=1)

    # Check status change, select first option
    expect(chemical_select).to_be_enabled()
    chemical_select.select_option(index=1)


def test_compare_full_funcionality(page):
    # Go to "Compare" page
    page.goto(f"{BASE_URL}/compare/", wait_until="domcontentloaded")

    # Check dropdown option selectors sequentially
    organism_select = page.locator("#compare-organism-select")
    category_select = page.locator("#compare-category-select")
    endpoint_select = page.locator("#compare-endpoint-select")

    # Check default dropdowns statuses
    expect(organism_select).to_be_enabled()
    expect(category_select).to_be_disabled()
    expect(endpoint_select).to_be_disabled()

    # Check organisms options, select first
    organism_count = organism_select.locator("option").count()
    assert organism_count > 1
    organism_select.select_option(index=1)

    # Check status change, select first option
    expect(category_select).to_be_enabled()
    category_select.select_option(index=1)
    
    # Check status change, select first option
    expect(endpoint_select).to_be_enabled()
    endpoint_select.select_option(index=1)

    # Check heatmap is rendered
    heatmap = page.locator("#compare-heatmap")
    expect(heatmap).to_be_visible()
    expect(heatmap.locator("svg.main-svg").first).to_be_visible(timeout=10_000)

    # Check heatmap options and heatmap state changes
    metric_select = page.locator("#compare-metric-select")
    cluster_select = page.locator("#compare-clustering-select")
    toxicity_select = page.locator("#compare-toxicity-category-select")
    chem_group_select = page.locator("#compare-rr-group-select")

    before_metric = heatmap_state(page)
    metric_select.select_option(index=2)
    wait_for_heatmap_state_change(page, before_metric)

    before_cluster = heatmap_state(page)
    cluster_select.select_option(index=2)
    wait_for_heatmap_state_change(page, before_cluster)

    before_toxicity = heatmap_state(page)
    toxicity_select.select_option(index=1)
    wait_for_heatmap_state_change(page, before_toxicity)

    before_group = heatmap_state(page)
    chem_group_select.select_option(index=1)
    wait_for_heatmap_state_change(page, before_group)

    # Check tabs
    pca_tab = page.get_by_role("tab", name="PCA")
    records_tab = page.get_by_role("tab", name="Database records")
    heatmap_tab = page.get_by_role("tab", name="Heatmap")

    pca_tab.click()
    expect(pca_tab).to_have_attribute("aria-selected", "true")
    expect(page.locator("#compare-panel-pca")).to_be_visible()

    pca_chart = page.locator("#compare-pca")
    expect(pca_chart).to_be_visible()
    expect(pca_chart.locator("svg.main-svg").first).to_be_visible(timeout=10_000)

    records_tab.click()
    expect(records_tab).to_have_attribute("aria-selected", "true")
    expect(page.locator("#compare-panel-records")).to_be_visible()

    records_table = page.locator("#compare-table")
    expect(records_table).to_be_visible()
    expect(records_table.locator("tbody tr").first).to_be_visible(timeout=10_000)

    heatmap_tab.click()
    expect(heatmap_tab).to_have_attribute("aria-selected", "true")
    expect(page.locator("#compare-panel-heatmap")).to_be_visible()
