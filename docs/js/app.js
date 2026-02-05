/**
 * Snowcast Frontend Application
 * Displays ski resort snow forecasts on an interactive map and table
 */

// Global state
let forecastData = null;
let map = null;
let markers = [];
let sortColumn = 'probability';
let sortDirection = 'desc';

// Unit conversion
const CM_TO_INCHES = 0.393701;

function toInches(resort) {
    // Handle both cm and in fields (in case data is already in inches)
    if (resort.expected_snow_in != null) {
        return Math.round(resort.expected_snow_in);
    }
    if (resort.expected_snow_cm != null) {
        return Math.round(resort.expected_snow_cm * CM_TO_INCHES);
    }
    return 0;
}

function dailyToInches(day) {
    if (day.in != null) {
        return Math.round(day.in);
    }
    if (day.cm != null) {
        return Math.round(day.cm * CM_TO_INCHES);
    }
    return 0;
}

// Initialize the application
document.addEventListener('DOMContentLoaded', init);

async function init() {
    initMap();
    await loadForecasts();
    setupEventListeners();
}

/**
 * Initialize Leaflet map
 */
function initMap() {
    map = L.map('map').setView([45, 10], 3);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
}

/**
 * Load forecast data from JSON file
 */
async function loadForecasts() {
    try {
        const response = await fetch('data/forecasts.json');
        if (!response.ok) {
            throw new Error('Failed to load forecast data');
        }

        forecastData = await response.json();
        updateLastUpdated(forecastData.generated_at);
        renderRegionCards();
        renderResortTable();
        renderMapMarkers();
        populateRegionFilter();
    } catch (error) {
        console.error('Error loading forecasts:', error);
        document.getElementById('region-cards').innerHTML =
            '<div class="loading">Failed to load forecast data. Please try again later.</div>';
    }
}

/**
 * Update the "last updated" timestamp in header
 */
function updateLastUpdated(timestamp) {
    if (!timestamp) return;

    const date = new Date(timestamp);
    const formatted = date.toLocaleString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZoneName: 'short'
    });

    document.getElementById('last-updated').textContent = `Last updated: ${formatted}`;
}

/**
 * Get color class based on snow probability
 */
function getSnowClass(probability) {
    if (probability >= 0.7) return 'snow-high';
    if (probability >= 0.4) return 'snow-medium';
    if (probability >= 0.1) return 'snow-low';
    return 'snow-none';
}

/**
 * Get color class based on snow amount (inches)
 */
function getSnowAmountClass(inches) {
    if (inches >= 6) return 'snow-high';
    if (inches >= 3) return 'snow-medium';
    if (inches >= 1) return 'snow-low';
    return 'snow-none';
}

/**
 * Get hex color for map markers
 */
function getMarkerColor(probability) {
    if (probability >= 0.7) return '#8158c7';
    if (probability >= 0.4) return '#a78bfa';
    if (probability >= 0.1) return '#c4b5fd';
    return '#E0E0E0';
}

/**
 * Render region cards sorted by snow probability
 */
function renderRegionCards() {
    const container = document.getElementById('region-cards');

    if (!forecastData || !forecastData.regions || forecastData.regions.length === 0) {
        container.innerHTML = '<div class="loading">No forecast data available.</div>';
        return;
    }

    container.innerHTML = forecastData.regions.map(region => `
        <div class="region-card" data-region="${region.id}">
            <h3>
                <span class="snow-indicator ${getSnowClass(region.avg_snow_probability)}"></span>
                ${region.name}
            </h3>
            <div class="stats">
                <span class="stat"><strong>${Math.round(region.avg_snow_probability * 100)}%</strong> avg chance</span>
                <span class="stat"><strong>${region.resorts_with_snow}</strong>/${region.total_resorts} resorts</span>
            </div>
            ${region.best_resort ? `
                <div class="best-resort">
                    Best: <strong>${region.best_resort.name}</strong> - ${toInches(region.best_resort)}" expected
                </div>
            ` : ''}
            <div class="prob-bar">
                <div class="prob-bar-fill ${getSnowClass(region.avg_snow_probability)}"
                     style="width: ${region.avg_snow_probability * 100}%"></div>
            </div>
        </div>
    `).join('');

    // Add click handlers to region cards
    container.querySelectorAll('.region-card').forEach(card => {
        card.addEventListener('click', () => {
            const regionId = card.dataset.region;
            filterByRegion(regionId);
        });
    });
}

/**
 * Flatten all resorts from regions into a single array
 */
function getAllResorts() {
    if (!forecastData || !forecastData.regions) return [];

    const resorts = [];
    forecastData.regions.forEach(region => {
        if (region.resorts) {
            region.resorts.forEach(resort => {
                resorts.push({
                    ...resort,
                    region_id: region.id,
                    region_name: region.name
                });
            });
        }
    });
    return resorts;
}

/**
 * Render the resorts table
 */
function renderResortTable() {
    const tbody = document.getElementById('resorts-body');
    let resorts = getAllResorts();

    // Apply filters
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const regionFilter = document.getElementById('region-filter').value;
    const snowFilter = parseFloat(document.getElementById('snow-filter').value) || 0;

    resorts = resorts.filter(resort => {
        if (searchTerm && !resort.name.toLowerCase().includes(searchTerm) &&
            !resort.country.toLowerCase().includes(searchTerm)) {
            return false;
        }
        if (regionFilter && resort.region_id !== regionFilter) {
            return false;
        }
        if (snowFilter && resort.snow_probability < snowFilter) {
            return false;
        }
        return true;
    });

    // Sort resorts
    resorts.sort((a, b) => {
        let valueA, valueB;
        switch (sortColumn) {
            case 'name':
                valueA = a.name.toLowerCase();
                valueB = b.name.toLowerCase();
                break;
            case 'country':
                valueA = a.country.toLowerCase();
                valueB = b.country.toLowerCase();
                break;
            case 'region':
                valueA = a.region_name.toLowerCase();
                valueB = b.region_name.toLowerCase();
                break;
            case 'probability':
                valueA = a.snow_probability;
                valueB = b.snow_probability;
                break;
            case 'snow':
                valueA = a.expected_snow_in ?? a.expected_snow_cm ?? 0;
                valueB = b.expected_snow_in ?? b.expected_snow_cm ?? 0;
                break;
            default:
                return 0;
        }

        if (valueA < valueB) return sortDirection === 'asc' ? -1 : 1;
        if (valueA > valueB) return sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    tbody.innerHTML = resorts.map(resort => `
        <tr>
            <td><strong>${resort.name}</strong></td>
            <td>${resort.country}</td>
            <td>${resort.region_name}</td>
            <td>
                <span class="snow-chance">
                    <span class="indicator ${getSnowClass(resort.snow_probability)}"></span>
                    ${Math.round(resort.snow_probability * 100)}%
                </span>
            </td>
            <td>${toInches(resort)}"</td>
            <td>
                <div class="daily-outlook">
                    ${renderDailyBars(resort.daily_forecast)}
                </div>
            </td>
        </tr>
    `).join('');
}

/**
 * Render daily forecast bars (scaled by snow amount, max 10")
 */
function renderDailyBars(dailyForecast) {
    if (!dailyForecast || dailyForecast.length === 0) {
        return '<span style="color: #999">No data</span>';
    }

    const maxInches = 10; // Scale: 10" = 100% height

    return dailyForecast.slice(0, 7).map(day => {
        const date = new Date(day.date + 'T12:00:00');
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
        const inches = dailyToInches(day);
        const tooltip = `${dayName}: ${inches}" expected`;
        // Scale height: 0" = 3%, 10"+ = 100%, with 10% minimum for any snow
        const height = inches > 0 ? Math.max(Math.min((inches / maxInches) * 100, 100), 10) : 3;

        return `
            <div class="daily-bar" data-tooltip="${tooltip}">
                <div class="fill ${getSnowAmountClass(inches)}" style="height: ${height}%"></div>
            </div>
        `;
    }).join('');
}

/**
 * Render map markers for all resorts
 */
function renderMapMarkers() {
    // Clear existing markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    const resorts = getAllResorts();

    resorts.forEach(resort => {
        const color = getMarkerColor(resort.snow_probability);

        const marker = L.circleMarker([resort.lat, resort.lon], {
            radius: 8,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(map);

        const popupContent = `
            <div class="resort-popup">
                <h4>${resort.name}</h4>
                <div class="popup-stats">
                    <p><strong>${Math.round(resort.snow_probability * 100)}%</strong> snow chance</p>
                    <p><strong>${toInches(resort)}"</strong> expected</p>
                    <p>${resort.country} | ${resort.elevation_m}m elevation</p>
                </div>
            </div>
        `;

        marker.bindPopup(popupContent);
        markers.push(marker);
    });
}

/**
 * Populate region filter dropdown
 */
function populateRegionFilter() {
    const select = document.getElementById('region-filter');

    if (!forecastData || !forecastData.regions) return;

    forecastData.regions.forEach(region => {
        const option = document.createElement('option');
        option.value = region.id;
        option.textContent = region.name;
        select.appendChild(option);
    });
}

/**
 * Filter table by region
 */
function filterByRegion(regionId) {
    document.getElementById('region-filter').value = regionId;
    renderResortTable();

    // Scroll to table
    document.querySelector('.resorts-section').scrollIntoView({ behavior: 'smooth' });
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Search input
    document.getElementById('search-input').addEventListener('input', () => {
        renderResortTable();
    });

    // Region filter
    document.getElementById('region-filter').addEventListener('change', () => {
        renderResortTable();
    });

    // Snow filter
    document.getElementById('snow-filter').addEventListener('change', () => {
        renderResortTable();
    });

    // Table sorting
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const column = th.dataset.sort;

            // Toggle direction if same column, otherwise default to desc
            if (sortColumn === column) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = column;
                sortDirection = column === 'name' || column === 'country' || column === 'region' ? 'asc' : 'desc';
            }

            // Update header classes
            document.querySelectorAll('th[data-sort]').forEach(header => {
                header.classList.remove('sort-asc', 'sort-desc');
            });
            th.classList.add(sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');

            renderResortTable();
        });
    });
}
