/**
 * StockPulse - Stock Market Dashboard
 * Alpha Vantage API Integration
 */

// ============================================
// Configuration
// ============================================
const CONFIG = {
    API_BASE: 'https://www.alphavantage.co/query',
    STORAGE_KEY: 'stockpulse_api_key',
    DEFAULT_SYMBOL: 'AAPL',
    CACHE_DURATION: 5 * 60 * 1000, // 5 minutes
};

// Demo data for when API is not available
const DEMO_DATA = {
    quote: {
        symbol: 'DEMO',
        name: 'Demo Company Inc.',
        price: 185.42,
        change: 2.34,
        changePercent: 1.28,
        open: 183.50,
        high: 186.20,
        low: 182.80,
        volume: 52436789,
        prevClose: 183.08,
        high52: 199.62,
    },
    history: generateDemoHistory(365)
};

// ============================================
// State Management
// ============================================
let state = {
    apiKey: localStorage.getItem(CONFIG.STORAGE_KEY) || '',
    currentSymbol: '',
    chartType: 'line',
    timeRange: '1W',
    priceChart: null,
    volumeChart: null,
    stockData: null,
    isDemo: false,
    cache: new Map(),
};

// ============================================
// DOM Elements
// ============================================
const elements = {
    searchInput: document.getElementById('stockSearch'),
    searchBtn: document.getElementById('searchBtn'),
    stockCard: document.getElementById('stockCard'),
    cardPlaceholder: document.getElementById('cardPlaceholder'),
    cardContent: document.getElementById('cardContent'),
    stockSymbol: document.getElementById('stockSymbol'),
    stockName: document.getElementById('stockName'),
    currentPrice: document.getElementById('currentPrice'),
    priceChange: document.getElementById('priceChange'),
    statOpen: document.getElementById('statOpen'),
    statHigh: document.getElementById('statHigh'),
    statLow: document.getElementById('statLow'),
    statVolume: document.getElementById('statVolume'),
    statPrevClose: document.getElementById('statPrevClose'),
    stat52High: document.getElementById('stat52High'),
    priceChart: document.getElementById('priceChart'),
    volumeChart: document.getElementById('volumeChart'),
    chartLoading: document.getElementById('chartLoading'),
    lastUpdated: document.getElementById('lastUpdated'),
    apiModal: document.getElementById('apiModal'),
    apiKeyInput: document.getElementById('apiKeyInput'),
    saveApiKey: document.getElementById('saveApiKey'),
    useDemo: document.getElementById('useDemo'),
    toastContainer: document.getElementById('toastContainer'),
    timeFilters: document.querySelectorAll('.time-btn'),
    typeFilters: document.querySelectorAll('.type-btn'),
    quickBtns: document.querySelectorAll('.quick-btn'),
};

// ============================================
// Initialization
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    // Check for API key
    if (!state.apiKey) {
        showApiModal();
    }
    
    // Set up event listeners
    setupEventListeners();
    
    // Update timestamp
    updateTimestamp();
    setInterval(updateTimestamp, 60000);
    
    // Load default or last viewed stock
    const lastSymbol = localStorage.getItem('stockpulse_last_symbol');
    if (lastSymbol && state.apiKey) {
        searchStock(lastSymbol);
    }
}

function setupEventListeners() {
    // Search functionality
    elements.searchBtn.addEventListener('click', handleSearch);
    elements.searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
    });
    
    // Quick pick buttons
    elements.quickBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const symbol = btn.dataset.symbol;
            elements.searchInput.value = symbol;
            searchStock(symbol);
        });
    });
    
    // Time range filters
    elements.timeFilters.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.timeFilters.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.timeRange = btn.dataset.range;
            if (state.stockData) {
                updateCharts();
            }
        });
    });
    
    // Chart type filters
    elements.typeFilters.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.typeFilters.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.chartType = btn.dataset.type;
            if (state.stockData) {
                updateCharts();
            }
        });
    });
    
    // API Modal
    elements.saveApiKey.addEventListener('click', saveApiKey);
    elements.useDemo.addEventListener('click', enableDemoMode);
    elements.apiKeyInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') saveApiKey();
    });
}

// ============================================
// API Functions
// ============================================
async function fetchStockQuote(symbol) {
    const cacheKey = `quote_${symbol}`;
    const cached = getFromCache(cacheKey);
    if (cached) return cached;
    
    const url = `${CONFIG.API_BASE}?function=GLOBAL_QUOTE&symbol=${symbol}&apikey=${state.apiKey}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data['Error Message']) {
            throw new Error('Invalid symbol');
        }
        
        if (data['Note']) {
            throw new Error('API rate limit reached. Please wait or use demo mode.');
        }
        
        const quote = data['Global Quote'];
        if (!quote || Object.keys(quote).length === 0) {
            throw new Error('No data found for this symbol');
        }
        
        const result = {
            symbol: quote['01. symbol'],
            price: parseFloat(quote['05. price']),
            change: parseFloat(quote['09. change']),
            changePercent: parseFloat(quote['10. change percent'].replace('%', '')),
            open: parseFloat(quote['02. open']),
            high: parseFloat(quote['03. high']),
            low: parseFloat(quote['04. low']),
            volume: parseInt(quote['06. volume']),
            prevClose: parseFloat(quote['08. previous close']),
        };
        
        setToCache(cacheKey, result);
        return result;
    } catch (error) {
        console.error('Error fetching quote:', error);
        throw error;
    }
}

async function fetchStockHistory(symbol) {
    const cacheKey = `history_${symbol}`;
    const cached = getFromCache(cacheKey);
    if (cached) return cached;
    
    const url = `${CONFIG.API_BASE}?function=TIME_SERIES_DAILY&symbol=${symbol}&outputsize=full&apikey=${state.apiKey}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data['Error Message']) {
            throw new Error('Invalid symbol');
        }
        
        if (data['Note']) {
            throw new Error('API rate limit reached');
        }
        
        const timeSeries = data['Time Series (Daily)'];
        if (!timeSeries) {
            throw new Error('No historical data found');
        }
        
        const history = Object.entries(timeSeries).map(([date, values]) => ({
            date: new Date(date),
            open: parseFloat(values['1. open']),
            high: parseFloat(values['2. high']),
            low: parseFloat(values['3. low']),
            close: parseFloat(values['4. close']),
            volume: parseInt(values['5. volume']),
        })).sort((a, b) => a.date - b.date);
        
        setToCache(cacheKey, history);
        return history;
    } catch (error) {
        console.error('Error fetching history:', error);
        throw error;
    }
}

async function fetchCompanyOverview(symbol) {
    const cacheKey = `overview_${symbol}`;
    const cached = getFromCache(cacheKey);
    if (cached) return cached;
    
    const url = `${CONFIG.API_BASE}?function=OVERVIEW&symbol=${symbol}&apikey=${state.apiKey}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data['Error Message'] || !data.Name) {
            return { name: symbol };
        }
        
        const result = {
            name: data.Name,
            high52: parseFloat(data['52WeekHigh']) || null,
            low52: parseFloat(data['52WeekLow']) || null,
            marketCap: data.MarketCapitalization,
            peRatio: data.PERatio,
        };
        
        setToCache(cacheKey, result);
        return result;
    } catch (error) {
        console.error('Error fetching overview:', error);
        return { name: symbol };
    }
}

// ============================================
// Search & Display Functions
// ============================================
function handleSearch() {
    const symbol = elements.searchInput.value.trim().toUpperCase();
    if (!symbol) {
        showToast('Please enter a stock symbol', 'error');
        return;
    }
    searchStock(symbol);
}

async function searchStock(symbol) {
    if (!state.apiKey && !state.isDemo) {
        showApiModal();
        return;
    }
    
    showLoading(true);
    
    try {
        if (state.isDemo) {
            // Use demo data
            await simulateDelay(500);
            state.stockData = {
                quote: { ...DEMO_DATA.quote, symbol },
                history: DEMO_DATA.history,
                overview: { name: `${symbol} Corporation (Demo)`, high52: DEMO_DATA.quote.high52 }
            };
        } else {
            // Fetch real data
            const [quote, history, overview] = await Promise.all([
                fetchStockQuote(symbol),
                fetchStockHistory(symbol),
                fetchCompanyOverview(symbol),
            ]);
            
            state.stockData = { quote, history, overview };
        }
        
        state.currentSymbol = symbol;
        localStorage.setItem('stockpulse_last_symbol', symbol);
        
        displayStockData();
        updateCharts();
        showToast(`Loaded ${symbol}`, 'success');
        
    } catch (error) {
        showToast(error.message || 'Failed to fetch stock data', 'error');
        console.error(error);
    } finally {
        showLoading(false);
    }
}

function displayStockData() {
    const { quote, overview } = state.stockData;
    
    // Show card content
    elements.cardPlaceholder.classList.add('hidden');
    elements.cardContent.classList.remove('hidden');
    
    // Update header
    elements.stockSymbol.textContent = quote.symbol || state.currentSymbol;
    elements.stockName.textContent = overview?.name || quote.symbol;
    
    // Update price
    elements.currentPrice.textContent = formatCurrency(quote.price);
    
    const isPositive = quote.change >= 0;
    const changeText = `${isPositive ? '+' : ''}${formatCurrency(quote.change)} (${isPositive ? '+' : ''}${quote.changePercent.toFixed(2)}%)`;
    elements.priceChange.textContent = changeText;
    elements.priceChange.className = `price-change ${isPositive ? 'positive' : 'negative'}`;
    
    // Update stats
    elements.statOpen.textContent = formatCurrency(quote.open);
    elements.statHigh.textContent = formatCurrency(quote.high);
    elements.statLow.textContent = formatCurrency(quote.low);
    elements.statVolume.textContent = formatNumber(quote.volume);
    elements.statPrevClose.textContent = formatCurrency(quote.prevClose);
    elements.stat52High.textContent = overview?.high52 ? formatCurrency(overview.high52) : '--';
}

// ============================================
// Chart Functions
// ============================================
function updateCharts() {
    const history = state.stockData.history;
    const filteredData = filterDataByRange(history, state.timeRange);
    
    renderPriceChart(filteredData);
    renderVolumeChart(filteredData);
}

function filterDataByRange(data, range) {
    const now = new Date();
    let startDate;
    
    switch (range) {
        case '5D':
            startDate = new Date(now.setDate(now.getDate() - 5));
            break;
        case '1W':
            startDate = new Date(now.setDate(now.getDate() - 7));
            break;
        case '1M':
            startDate = new Date(now.setMonth(now.getMonth() - 1));
            break;
        case '3M':
            startDate = new Date(now.setMonth(now.getMonth() - 3));
            break;
        case '6M':
            startDate = new Date(now.setMonth(now.getMonth() - 6));
            break;
        case '1Y':
            startDate = new Date(now.setFullYear(now.getFullYear() - 1));
            break;
        default:
            startDate = new Date(now.setDate(now.getDate() - 7));
    }
    
    return data.filter(d => d.date >= startDate);
}

function renderPriceChart(data) {
    const ctx = elements.priceChart.getContext('2d');
    
    // Destroy existing chart
    if (state.priceChart) {
        state.priceChart.destroy();
    }
    
    const labels = data.map(d => d.date);
    const prices = data.map(d => d.close);
    
    const isPositive = prices[prices.length - 1] >= prices[0];
    const lineColor = isPositive ? '#00d4aa' : '#ef4444';
    const gradientColor = isPositive ? 'rgba(0, 212, 170, 0.1)' : 'rgba(239, 68, 68, 0.1)';
    
    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 350);
    gradient.addColorStop(0, gradientColor);
    gradient.addColorStop(1, 'transparent');
    
    let datasetConfig;
    
    switch (state.chartType) {
        case 'bar':
            datasetConfig = {
                type: 'bar',
                data: prices,
                backgroundColor: prices.map((price, i) => 
                    i === 0 || price >= prices[i - 1] ? 'rgba(0, 212, 170, 0.7)' : 'rgba(239, 68, 68, 0.7)'
                ),
                borderColor: prices.map((price, i) => 
                    i === 0 || price >= prices[i - 1] ? '#00d4aa' : '#ef4444'
                ),
                borderWidth: 1,
            };
            break;
        case 'area':
            datasetConfig = {
                type: 'line',
                data: prices,
                borderColor: lineColor,
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: lineColor,
            };
            break;
        default: // line
            datasetConfig = {
                type: 'line',
                data: prices,
                borderColor: lineColor,
                backgroundColor: 'transparent',
                borderWidth: 2,
                fill: false,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: lineColor,
            };
    }
    
    state.priceChart = new Chart(ctx, {
        type: datasetConfig.type,
        data: {
            labels,
            datasets: [{
                label: 'Price',
                ...datasetConfig,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: {
                    display: false,
                },
                tooltip: {
                    backgroundColor: '#1a2235',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#1e293b',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: (items) => formatDate(items[0].label),
                        label: (item) => `Price: ${formatCurrency(item.raw)}`,
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: getTimeUnit(state.timeRange),
                        displayFormats: {
                            day: 'MMM d',
                            week: 'MMM d',
                            month: 'MMM yyyy',
                        }
                    },
                    grid: {
                        color: 'rgba(30, 41, 59, 0.5)',
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 11,
                        }
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(30, 41, 59, 0.5)',
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 11,
                        },
                        callback: (value) => '$' + value.toFixed(0),
                    }
                }
            }
        }
    });
}

function renderVolumeChart(data) {
    const ctx = elements.volumeChart.getContext('2d');
    
    // Destroy existing chart
    if (state.volumeChart) {
        state.volumeChart.destroy();
    }
    
    const labels = data.map(d => d.date);
    const volumes = data.map(d => d.volume);
    const prices = data.map(d => d.close);
    
    state.volumeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Volume',
                data: volumes,
                backgroundColor: prices.map((price, i) => 
                    i === 0 || price >= prices[i - 1] ? 'rgba(0, 212, 170, 0.5)' : 'rgba(239, 68, 68, 0.5)'
                ),
                borderColor: prices.map((price, i) => 
                    i === 0 || price >= prices[i - 1] ? '#00d4aa' : '#ef4444'
                ),
                borderWidth: 1,
                borderRadius: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false,
                },
                tooltip: {
                    backgroundColor: '#1a2235',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#1e293b',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: (items) => formatDate(items[0].label),
                        label: (item) => `Volume: ${formatNumber(item.raw)}`,
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: getTimeUnit(state.timeRange),
                    },
                    grid: {
                        display: false,
                    },
                    ticks: {
                        display: false,
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(30, 41, 59, 0.5)',
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10,
                        },
                        callback: (value) => formatCompactNumber(value),
                    }
                }
            }
        }
    });
}

function getTimeUnit(range) {
    switch (range) {
        case '5D':
        case '1W':
            return 'day';
        case '1M':
        case '3M':
            return 'week';
        default:
            return 'month';
    }
}

// ============================================
// UI Helper Functions
// ============================================
function showLoading(show) {
    elements.chartLoading.classList.toggle('hidden', !show);
}

function showApiModal() {
    elements.apiModal.classList.remove('hidden');
}

function hideApiModal() {
    elements.apiModal.classList.add('hidden');
}

function saveApiKey() {
    const key = elements.apiKeyInput.value.trim();
    if (!key) {
        showToast('Please enter an API key', 'error');
        return;
    }
    
    state.apiKey = key;
    state.isDemo = false;
    localStorage.setItem(CONFIG.STORAGE_KEY, key);
    hideApiModal();
    showToast('API key saved!', 'success');
}

function enableDemoMode() {
    state.isDemo = true;
    state.apiKey = 'demo';
    hideApiModal();
    showToast('Demo mode enabled', 'success');
    searchStock('DEMO');
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '✓',
        error: '✕',
        info: 'ℹ',
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
    `;
    
    elements.toastContainer.appendChild(toast);
    
    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function updateTimestamp() {
    const now = new Date();
    const options = { 
        weekday: 'short', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit', 
        minute: '2-digit',
    };
    elements.lastUpdated.textContent = now.toLocaleDateString('en-US', options);
}

// ============================================
// Utility Functions
// ============================================
function formatCurrency(value) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
    }).format(value);
}

function formatNumber(value) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    return new Intl.NumberFormat('en-US').format(value);
}

function formatCompactNumber(value) {
    if (value >= 1e9) return (value / 1e9).toFixed(1) + 'B';
    if (value >= 1e6) return (value / 1e6).toFixed(1) + 'M';
    if (value >= 1e3) return (value / 1e3).toFixed(1) + 'K';
    return value.toString();
}

function formatDate(date) {
    const d = new Date(date);
    return d.toLocaleDateString('en-US', { 
        weekday: 'short',
        month: 'short', 
        day: 'numeric',
        year: 'numeric',
    });
}

function simulateDelay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Cache functions
function getFromCache(key) {
    const item = state.cache.get(key);
    if (!item) return null;
    if (Date.now() - item.timestamp > CONFIG.CACHE_DURATION) {
        state.cache.delete(key);
        return null;
    }
    return item.data;
}

function setToCache(key, data) {
    state.cache.set(key, {
        data,
        timestamp: Date.now(),
    });
}

// Generate demo historical data
function generateDemoHistory(days) {
    const history = [];
    let price = 150;
    const now = new Date();
    
    for (let i = days; i >= 0; i--) {
        const date = new Date(now);
        date.setDate(date.getDate() - i);
        
        // Skip weekends
        if (date.getDay() === 0 || date.getDay() === 6) continue;
        
        const change = (Math.random() - 0.48) * 5;
        price = Math.max(100, Math.min(220, price + change));
        
        const volatility = Math.random() * 3;
        
        history.push({
            date,
            open: price - volatility,
            high: price + volatility + Math.random() * 2,
            low: price - volatility - Math.random() * 2,
            close: price,
            volume: Math.floor(30000000 + Math.random() * 50000000),
        });
    }
    
    return history;
}

// ============================================
// Export for testing (if needed)
// ============================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        fetchStockQuote,
        fetchStockHistory,
        formatCurrency,
        formatNumber,
    };
}
