// Global variables
let currentData = null;
let temporalChart = null;
let creativesChart = null;
let distributionChart = null;
let temporalDetailedChart = null;
let costsChart = null;
let conversionChart = null;
let campaignsChart = null;
let filteredData = null;

// DOM Elements
const uploadSection = document.getElementById('uploadSection');
const loadingSection = document.getElementById('loadingSection');
const dashboardSection = document.getElementById('dashboardSection');
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const kpisGrid = document.getElementById('kpisGrid');
const dataTable = document.getElementById('dataTable');
const tableHead = document.getElementById('tableHead');
const tableBody = document.getElementById('tableBody');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initializeUpload();
    initializeCharts();
    initializeFilters();
    initializeAutoUpload();
});

// Upload functionality
function initializeUpload() {
    // Click to upload
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });
}

function handleFileUpload(file) {
    // Validate file type
    const allowedTypes = [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'text/csv'
    ];
    
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(xlsx|xls|csv)$/)) {
        alert('Por favor, selecione um arquivo Excel (.xlsx, .xls) ou CSV válido.');
        return;
    }

    // Show loading
    showLoading();

    // Upload file
    const formData = new FormData();
    formData.append('file', file);

    console.log('Starting upload...');
    console.log('File details:', {
        name: file.name,
        size: file.size,
        type: file.type
    });
    
    // Criar um AbortController para timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 segundos
    
    fetch('/upload', {
        method: 'POST',
        body: formData,
        signal: controller.signal
    })
    .then(response => {
        console.log('Upload response received:', response.status, response.statusText);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.text();
    })
    .then(text => {
        clearTimeout(timeoutId); // Limpar timeout
        try {
            const data = JSON.parse(text);
            if (data.success) {
                currentData = data.data;
                showDashboard();
            } else {
                throw new Error(data.error || 'Erro ao processar arquivo');
            }
        } catch (parseError) {
            console.error('JSON Parse Error:', parseError);
            console.error('Response text:', text);
            throw new Error('Resposta do servidor inválida. Verifique o arquivo e tente novamente.');
        }
    })
    .catch(error => {
        clearTimeout(timeoutId); // Limpar timeout
        console.error('Upload Error Details:', error);
        console.error('Error type:', typeof error);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
        
        let errorMessage = 'Erro desconhecido';
        if (error.name === 'AbortError') {
            errorMessage = 'Upload cancelado por timeout (30s). Arquivo muito grande ou servidor lento.';
        } else if (error.message.includes('Failed to fetch')) {
            errorMessage = 'Erro de conexão com o servidor. Verifique se o servidor está rodando em http://localhost:5000';
        } else {
            errorMessage = 'Erro ao processar arquivo: ' + error.message;
        }
        
        alert(errorMessage);
        showUpload();
    });
}

function showLoading() {
    uploadSection.style.display = 'none';
    dashboardSection.style.display = 'none';
    loadingSection.style.display = 'block';
}

function showUpload() {
    uploadSection.style.display = 'block';
    dashboardSection.style.display = 'none';
    loadingSection.style.display = 'none';
}

function showDashboard() {
    uploadSection.style.display = 'none';
    loadingSection.style.display = 'none';
    dashboardSection.style.display = 'block';
    
    filteredData = currentData; // Initialize filtered data
    populateFilters();
    renderKPIs();
    renderCharts();
    renderTable();
    
    // Add fade-in animation
    dashboardSection.classList.add('fade-in');
}

// KPIs rendering
function renderKPIs() {
    if (!filteredData) return;

    const kpis = filteredData.kpis;
    const columns = filteredData.columns;
    
    kpisGrid.innerHTML = '';

    // Total rows
    const totalRowsCard = createKPICard(
        'Total de Registros',
        filteredData.total_rows,
        'fas fa-database',
        '#3B82F6'
    );
    kpisGrid.appendChild(totalRowsCard);

    // Total leads
    if (kpis.total_leads !== undefined) {
        const leadsCard = createKPICard(
            'Total de Leads',
            kpis.total_leads.toLocaleString(),
            'fas fa-users',
            '#10B981'
        );
        kpisGrid.appendChild(leadsCard);
    }

    // Total MQLs
    if (kpis.total_mqls !== undefined) {
        const mqlsCard = createKPICard(
            'Total de MQLs',
            kpis.total_mqls.toLocaleString(),
            'fas fa-user-check',
            '#8B5CF6'
        );
        kpisGrid.appendChild(mqlsCard);
    }

    // Investment
    if (kpis.investimento_total !== undefined) {
        const investmentCard = createKPICard(
            'Investimento Total',
            'R$ ' + kpis.investimento_total.toLocaleString('pt-BR', {minimumFractionDigits: 2}),
            'fas fa-dollar-sign',
            '#F97316'
        );
        kpisGrid.appendChild(investmentCard);
    }
    
    // Custo por MQL
    if (kpis.custo_por_mql !== undefined && kpis.custo_por_mql > 0) {
        const custoMQLCard = createKPICard(
            'Custo por MQL',
            'R$ ' + kpis.custo_por_mql.toLocaleString('pt-BR', {minimumFractionDigits: 2}),
            'fas fa-chart-line',
            '#8B5CF6'
        );
        kpisGrid.appendChild(custoMQLCard);
    }

    // Cost per lead
    if (kpis.total_leads && kpis.investimento_total) {
        const cpl = kpis.investimento_total / kpis.total_leads;
        const cplCard = createKPICard(
            'Custo por Lead',
            'R$ ' + cpl.toLocaleString('pt-BR', {minimumFractionDigits: 2}),
            'fas fa-tag',
            '#EF4444'
        );
        kpisGrid.appendChild(cplCard);
    }

    // Date range
    if (currentData.summary && currentData.summary.temporal) {
        const dateRange = currentData.summary.temporal.length;
        const dateCard = createKPICard(
            'Período Analisado',
            dateRange + ' dias',
            'fas fa-calendar',
            '#6B7280'
        );
        kpisGrid.appendChild(dateCard);
    }
}

function createKPICard(title, value, icon, color) {
    const card = document.createElement('div');
    card.className = 'kpi-card';
    
    // Mapear cores para a paleta BeHonest
    const brandColors = {
        '#3B82F6': '#2374b9', // Blue
        '#10B981': '#edb125', // Mustard (para leads)
        '#8B5CF6': '#001c54', // Primary (para MQLs e custo MQL)
        '#F97316': '#de5e36', // Orange
        '#EF4444': '#b2b2b2', // Gray (para custo lead)
        '#6B7280': '#001c54'  // Primary (para período)
    };
    
    const brandColor = brandColors[color] || '#001c54';
    
    card.innerHTML = `
        <div class="kpi-header">
            <div class="kpi-title">${title}</div>
            <div class="kpi-icon" style="background: ${brandColor}; color: white;">
                <i class="${icon}"></i>
            </div>
        </div>
        <div class="kpi-value">${value}</div>
    `;
    
    return card;
}

// Charts rendering
function initializeCharts() {
    // Temporal chart
    const temporalCtx = document.getElementById('temporalChart').getContext('2d');
    temporalChart = new Chart(temporalCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Criativos por Dia',
                data: [],
                borderColor: '#F97316',
                backgroundColor: 'rgba(249, 115, 22, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                },
                x: {
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                }
            }
        }
    });

    // Distribution chart
    const distributionCtx = document.getElementById('distributionChart').getContext('2d');
    distributionChart = new Chart(distributionCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Distribuição',
                data: [],
                backgroundColor: 'rgba(59, 130, 246, 0.8)',
                borderColor: '#3B82F6',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                },
                x: {
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                }
            }
        }
    });

    // Temporal Detailed chart
    const temporalDetailedCtx = document.getElementById('temporalDetailedChart').getContext('2d');
    temporalDetailedChart = new Chart(temporalDetailedCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Evolução Detalhada',
                data: [],
                borderColor: '#8B5CF6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                },
                x: {
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                }
            }
        }
    });

    // Costs chart
    const costsCtx = document.getElementById('costsChart').getContext('2d');
    costsChart = new Chart(costsCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Custos',
                data: [],
                backgroundColor: 'rgba(239, 68, 68, 0.8)',
                borderColor: '#EF4444',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                },
                x: {
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                }
            }
        }
    });

    // Conversion chart
    const conversionCtx = document.getElementById('conversionChart').getContext('2d');
    conversionChart = new Chart(conversionCtx, {
        type: 'doughnut',
        data: {
            labels: ['Leads', 'MQLs'],
            datasets: [{
                data: [0, 0],
                backgroundColor: ['#10B981', '#8B5CF6'],
                borderWidth: 2,
                borderColor: '#FFFFFF'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });

    // Creatives chart
    const creativesCtx = document.getElementById('creativesChart').getContext('2d');
    creativesChart = new Chart(creativesCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Leads Gerados',
                data: [],
                backgroundColor: 'rgba(16, 185, 129, 0.8)',
                borderColor: '#10B981',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                },
                x: {
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280',
                        maxRotation: 90,
                        minRotation: 45
                    }
                }
            }
        }
    });

    // Campaigns chart
    const campaignsCtx = document.getElementById('campaignsChart').getContext('2d');
    campaignsChart = new Chart(campaignsCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Performance',
                data: [],
                backgroundColor: 'rgba(249, 115, 22, 0.8)',
                borderColor: '#F97316',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280'
                    }
                },
                x: {
                    grid: {
                        color: '#E5E7EB'
                    },
                    ticks: {
                        color: '#6B7280',
                        maxRotation: 90,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

function renderCharts() {
    if (!filteredData) return;

    // Update all charts based on current analysis type
    const analysisType = document.getElementById('analysisType').value;
    
    switch(analysisType) {
        case 'overview':
            renderOverviewCharts();
            break;
        case 'temporal':
            renderTemporalCharts();
            break;
        case 'financial':
            renderFinancialCharts();
            break;
        case 'creatives':
            renderCreativesCharts();
            break;
    }
}

function renderOverviewCharts() {
    // Update temporal chart
    if (filteredData.summary && filteredData.summary.temporal) {
        const temporalData = filteredData.summary.temporal;
        temporalChart.data.labels = temporalData.map(item => item.Data);
        temporalChart.data.datasets[0].data = temporalData.map(item => item.Criativos);
        temporalChart.update();
    }
    
    // Update distribution chart with leads data
    renderLeadsDistributionChart();
}

function renderLeadsDistributionChart() {
    if (!filteredData || !filteredData.raw_data) return;
    
    // Get date and leads columns
    const dateCol = filteredData.date_column;
    const leadsCol = filteredData.leads_columns?.lead;
    
    if (!dateCol || !leadsCol || !filteredData.raw_data.length) return;
    
    // Helper function to format date to DD/MM/YYYY
    function formatDate(dateStr) {
        if (!dateStr) return '';
        
        // If already in DD/MM/YYYY format, return as is
        if (dateStr.match(/^\d{2}\/\d{2}\/\d{4}$/)) {
            return dateStr;
        }
        
        // If in YYYY-MM-DD format (with or without time)
        if (dateStr.match(/^\d{4}-\d{2}-\d{2}/)) {
            const parts = dateStr.split(' ')[0].split('-'); // Remove time if present
            const year = parts[0];
            const month = parts[1];
            const day = parts[2];
            return `${day}/${month}/${year}`;
        }
        
        // Try to parse and format
        try {
            const date = new Date(dateStr);
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const year = date.getFullYear();
            return `${day}/${month}/${year}`;
        } catch (e) {
            return dateStr;
        }
    }
    
    // Group leads by date
    const leadsByDate = {};
    filteredData.raw_data.forEach(row => {
        let date = row[dateCol] || row['Data_Processada'];
        if (!date) return;
        
        // Format date to DD/MM/YYYY
        date = formatDate(date);
        
        const leads = parseFloat(row[leadsCol] || row['LEAD'] || 0);
        if (leadsByDate[date]) {
            leadsByDate[date] += leads;
        } else {
            leadsByDate[date] = leads;
        }
    });
    
    // Convert to array and sort by date (convert to comparable format for sorting)
    const dates = Object.keys(leadsByDate).sort((a, b) => {
        const [dayA, monthA, yearA] = a.split('/').map(Number);
        const [dayB, monthB, yearB] = b.split('/').map(Number);
        const dateA = new Date(yearA, monthA - 1, dayA);
        const dateB = new Date(yearB, monthB - 1, dayB);
        return dateA - dateB;
    });
    
    // Format dates for display
    const labels = dates;
    const values = dates.map(date => leadsByDate[date] || 0);
    
    // Update distribution chart
    distributionChart.data.labels = labels;
    distributionChart.data.datasets[0].data = values;
    distributionChart.data.datasets[0].backgroundColor = 'rgba(0, 51, 102, 0.8)'; // Navy blue
    distributionChart.data.datasets[0].borderColor = '#003366';
    distributionChart.update();
}

function renderTemporalCharts() {
    if (filteredData.summary && filteredData.summary.temporal) {
        const temporalData = filteredData.summary.temporal;
        
        // Update detailed chart
        temporalDetailedChart.data.labels = temporalData.map(item => item.Data);
        temporalDetailedChart.data.datasets[0].data = temporalData.map(item => item.Criativos);
        temporalDetailedChart.update();
        
        // Update metrics
        const totalDays = temporalData.length;
        const totalCreatives = temporalData.reduce((sum, item) => sum + item.Criativos, 0);
        const avgCreatives = totalCreatives / totalDays;
        const peakDay = temporalData.reduce((max, item) => 
            item.Criativos > max.Criativos ? item : max, temporalData[0]);
        
        document.getElementById('periodDays').textContent = totalDays + ' dias';
        document.getElementById('avgCreatives').textContent = avgCreatives.toFixed(1);
        document.getElementById('peakDay').textContent = peakDay.Data + ' (' + peakDay.Criativos + ')';
    }
}

function renderFinancialCharts() {
    if (filteredData.kpis) {
        const kpis = filteredData.kpis;
        
        // Update conversion chart
        if (kpis.total_leads && kpis.total_mqls) {
            conversionChart.data.datasets[0].data = [kpis.total_leads, kpis.total_mqls];
            conversionChart.update();
        }
        
        // Update financial metrics
        if (kpis.investimento_total && kpis.total_leads) {
            const cpl = kpis.investimento_total / kpis.total_leads;
            document.getElementById('avgCPL').textContent = 'R$ ' + cpl.toLocaleString('pt-BR', {minimumFractionDigits: 2});
        }
        
        if (kpis.investimento_total && kpis.total_mqls) {
            const cpmql = kpis.investimento_total / kpis.total_mqls;
            document.getElementById('avgCPMQL').textContent = 'R$ ' + cpmql.toLocaleString('pt-BR', {minimumFractionDigits: 2});
        }
        
        // Custo por MQL (dados do backend)
        if (kpis.custo_por_mql && kpis.custo_por_mql > 0) {
            document.getElementById('custoPorMQL').textContent = 'R$ ' + kpis.custo_por_mql.toLocaleString('pt-BR', {minimumFractionDigits: 2});
        } else {
            document.getElementById('custoPorMQL').textContent = 'N/A';
        }
    }
    
    // Render costs chart with last week data
    renderCostsChart();
}

function renderCostsChart() {
    if (!filteredData || !filteredData.raw_data) return;
    
    // Get date and investment columns
    const dateCol = filteredData.date_column;
    const costCol = 'Investimento';
    
    if (!dateCol || !filteredData.raw_data.length) return;
    
    // Helper function to format date to DD/MM/YYYY
    function formatDate(dateStr) {
        if (!dateStr) return '';
        
        // If already in DD/MM/YYYY format, return as is
        if (dateStr.match(/^\d{2}\/\d{2}\/\d{4}$/)) {
            return dateStr;
        }
        
        // If in YYYY-MM-DD format (with or without time)
        if (dateStr.match(/^\d{4}-\d{2}-\d{2}/)) {
            const parts = dateStr.split(' ')[0].split('-'); // Remove time if present
            const year = parts[0];
            const month = parts[1];
            const day = parts[2];
            return `${day}/${month}/${year}`;
        }
        
        // Try to parse and format
        try {
            const date = new Date(dateStr);
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const year = date.getFullYear();
            return `${day}/${month}/${year}`;
        } catch (e) {
            return dateStr;
        }
    }
    
    // Group investment by date
    const investmentByDate = {};
    filteredData.raw_data.forEach(row => {
        let date = row[dateCol] || row['Data_Processada'];
        if (!date) return;
        
        // Format date to DD/MM/YYYY
        date = formatDate(date);
        
        const investimento = parseFloat(row[costCol] || row['Investimento'] || 0);
        if (investmentByDate[date]) {
            investmentByDate[date] += investimento;
        } else {
            investmentByDate[date] = investimento;
        }
    });
    
    // Convert to array and sort by date (convert to comparable format for sorting)
    const dates = Object.keys(investmentByDate).sort((a, b) => {
        const [dayA, monthA, yearA] = a.split('/').map(Number);
        const [dayB, monthB, yearB] = b.split('/').map(Number);
        const dateA = new Date(yearA, monthA - 1, dayA);
        const dateB = new Date(yearB, monthB - 1, dayB);
        return dateA - dateB;
    });
    
    // Get last 7 days
    const last7Days = dates.slice(-7);
    
    // Format dates for display
    const labels = last7Days;
    const values = last7Days.map(date => investmentByDate[date] || 0);
    
    // Update costs chart
    costsChart.data.labels = labels;
    costsChart.data.datasets[0].data = values;
    costsChart.data.datasets[0].backgroundColor = 'rgba(237, 177, 37, 0.8)'; // Mustard color
    costsChart.data.datasets[0].borderColor = '#edb125';
    costsChart.update();
}

function renderCreativesCharts() {
    if (filteredData.creative_analysis && filteredData.creative_analysis.top_creatives) {
        const analysis = filteredData.creative_analysis;
        const creativesData = analysis.top_creatives;
        const labels = Object.keys(creativesData).slice(0, 10);
        const values = labels.map(label => creativesData[label]);
        
        // Keep full labels for chart
        creativesChart.data.labels = labels;
        creativesChart.data.datasets[0].data = values;
        creativesChart.update();
        
        // Update basic metrics
        document.getElementById('totalCreatives').textContent = analysis.total_creatives || 0;
        document.getElementById('avgPerformance').textContent = (analysis.avg_leads_per_creative || 0).toFixed(1) + ' leads';
        
               // Update top creative metrics - Simplificado
               if (analysis.top_lead_creative) {
                   const topLead = analysis.top_lead_creative;
                   document.getElementById('topLeadCreative').textContent = `${topLead.name} - ${topLead.leads} leads`;
                   document.getElementById('topLeadCreativeName').textContent = topLead.name;
                   document.getElementById('topLeadCreativeLeads').textContent = topLead.leads;
                   document.getElementById('topLeadCreativeMQLs').textContent = topLead.mqls;
                   document.getElementById('topLeadCreativeAppearances').textContent = topLead.appearances;
                   document.getElementById('topLeadCreativeLeadsPerApp').textContent = topLead.leads_per_appearance.toFixed(2);
                   document.getElementById('topLeadCreativeConversion').textContent = topLead.conversion_rate.toFixed(1) + '%';
               }
               
               if (analysis.top_mql_creative) {
                   const topMQL = analysis.top_mql_creative;
                   document.getElementById('topMQLCreative').textContent = `${topMQL.name} - ${topMQL.mqls} MQLs`;
                   document.getElementById('topMQLCreativeName').textContent = topMQL.name;
                   document.getElementById('topMQLCreativeLeads').textContent = topMQL.leads;
                   document.getElementById('topMQLCreativeMQLs').textContent = topMQL.mqls;
                   document.getElementById('topMQLCreativeAppearances').textContent = topMQL.appearances;
                   document.getElementById('topMQLCreativeMQLsPerApp').textContent = topMQL.mqls_per_appearance.toFixed(2);
                   document.getElementById('topMQLCreativeConversion').textContent = topMQL.conversion_rate.toFixed(1) + '%';
               }
        
               // Render detailed creatives table
               renderCreativesTable(analysis.creative_details);
               
               // Render top 5 ranking
               renderTopCreativesRanking(analysis.creative_details);
               
               // Update campaigns chart (placeholder - would need campaign data)
               campaignsChart.data.labels = ['Campanha A', 'Campanha B', 'Campanha C'];
               campaignsChart.data.datasets[0].data = [10, 15, 8];
               campaignsChart.update();
    }
}

function renderCreativesTable(creativeDetails) {
    const tableBody = document.getElementById('creativesTableBody');
    if (!creativeDetails || creativeDetails.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="8">Nenhum dado de criativo disponível</td></tr>';
        return;
    }
    
    tableBody.innerHTML = '';
    
    creativeDetails.forEach(creative => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="creative-name-cell">${creative.creative || creative.campaign || 'N/A'}</td>
            <td class="number-cell">${creative.Total_Leads || 0}</td>
            <td class="number-cell">${creative.Total_MQLs || 0}</td>
            <td class="number-cell">${creative.Qtd_Aparicoes || 0}</td>
            <td class="number-cell">${(creative.Leads_por_Aparicao || 0).toFixed(2)}</td>
            <td class="number-cell">${(creative.MQLs_por_Aparicao || 0).toFixed(2)}</td>
            <td class="number-cell">${(creative.Taxa_Conversao_Lead_MQL || 0).toFixed(1)}%</td>
            <td class="number-cell">R$ ${(creative.Total_Investimento || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
        `;
        tableBody.appendChild(row);
    });
}

function renderTopCreativesRanking(creativeDetails) {
    const rankingContainer = document.getElementById('topCreativesRanking');
    if (!creativeDetails || creativeDetails.length === 0) {
        rankingContainer.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 2rem;">Nenhum dado de criativo disponível</p>';
        return;
    }
    
    // Ordenar por total de leads e pegar top 5
    const topCreatives = creativeDetails
        .sort((a, b) => (b.Total_Leads || 0) - (a.Total_Leads || 0))
        .slice(0, 5);
    
    rankingContainer.innerHTML = '';
    
    topCreatives.forEach((creative, index) => {
        const rank = index + 1;
        const creativeName = creative.creative || creative.campaign || 'N/A';
        
        const rankingItem = document.createElement('div');
        rankingItem.className = `ranking-item rank-${rank}`;
        
        rankingItem.innerHTML = `
            <div class="rank-position rank-${rank}">
                ${rank}
            </div>
            <div class="ranking-info">
                <div class="creative-name-rank">
                    ${creativeName}
                </div>
                <div class="ranking-metric">
                    <span class="value">${creative.Total_Leads || 0}</span>
                    <span class="label">Leads</span>
                </div>
                <div class="ranking-metric">
                    <span class="value">${creative.Total_MQLs || 0}</span>
                    <span class="label">MQLs</span>
                </div>
                <div class="ranking-metric">
                    <span class="value">${(creative.Taxa_Conversao_Lead_MQL || 0).toFixed(1)}%</span>
                    <span class="label">Conversão</span>
                </div>
            </div>
        `;
        
        rankingContainer.appendChild(rankingItem);
    });
}

function exportCreativesTable() {
    console.log('Exporting creatives table...');
    alert('Funcionalidade de exportação da tabela de criativos será implementada em breve!');
}

// Table rendering
function renderTable() {
    if (!filteredData || !filteredData.raw_data) return;

    const data = filteredData.raw_data;
    const columns = filteredData.columns;

    // Clear existing content
    tableHead.innerHTML = '';
    tableBody.innerHTML = '';

    // Create header
    const headerRow = document.createElement('tr');
    columns.forEach(column => {
        const th = document.createElement('th');
        th.textContent = column;
        headerRow.appendChild(th);
    });
    tableHead.appendChild(headerRow);

    // Create body
    data.forEach(row => {
        const tr = document.createElement('tr');
        columns.forEach(column => {
            const td = document.createElement('td');
            td.textContent = row[column] || '';
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });

    // Add search functionality
    const searchInput = document.getElementById('searchInput');
    const rowsSelect = document.getElementById('rowsSelect');
    
    searchInput.addEventListener('input', filterTable);
    rowsSelect.addEventListener('change', filterTable);
}

function filterTable() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const maxRows = document.getElementById('rowsSelect').value;
    const rows = tableBody.querySelectorAll('tr');
    
    let visibleCount = 0;
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const isVisible = text.includes(searchTerm);
        
        if (isVisible && (maxRows === 'all' || visibleCount < parseInt(maxRows))) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
}

// Filters functionality
function initializeFilters() {
    const analysisTypeSelect = document.getElementById('analysisType');
    analysisTypeSelect.addEventListener('change', switchAnalysisType);
    
    const dateFilter = document.getElementById('dateFilter');
    dateFilter.addEventListener('change', applyFilters);
}

function populateFilters() {
    if (!currentData) return;
    
    // Populate date filter
    const dateFilter = document.getElementById('dateFilter');
    dateFilter.innerHTML = '<option value="all">Todas as datas</option>';
    
    if (currentData.summary && currentData.summary.temporal) {
        currentData.summary.temporal.forEach(item => {
            const option = document.createElement('option');
            option.value = item.Data;
            option.textContent = item.Data;
            dateFilter.appendChild(option);
        });
    }
}

function switchAnalysisType() {
    const analysisType = document.getElementById('analysisType').value;
    
    // Hide all sections
    document.getElementById('overviewSection').style.display = 'none';
    document.getElementById('temporalSection').style.display = 'none';
    document.getElementById('financialSection').style.display = 'none';
    document.getElementById('creativesSection').style.display = 'none';
    
    // Show selected section
    switch(analysisType) {
        case 'overview':
            document.getElementById('overviewSection').style.display = 'block';
            break;
        case 'temporal':
            document.getElementById('temporalSection').style.display = 'block';
            break;
        case 'financial':
            document.getElementById('financialSection').style.display = 'block';
            break;
        case 'creatives':
            document.getElementById('creativesSection').style.display = 'block';
            break;
    }
    
    // Re-render charts for the selected section
    renderCharts();
}

function applyFilters() {
    if (!currentData) return;
    
    const dateFilter = document.getElementById('dateFilter').value;
    
    // Create filtered data
    filteredData = JSON.parse(JSON.stringify(currentData)); // Deep copy
    
    // Apply date filter
    if (dateFilter !== 'all' && filteredData.summary && filteredData.summary.temporal) {
        filteredData.summary.temporal = filteredData.summary.temporal.filter(item => item.Data === dateFilter);
    }
    
    // Re-render charts with filtered data
    renderCharts();
    renderKPIs();
}

function resetFilters() {
    document.getElementById('dateFilter').value = 'all';
    
    filteredData = currentData; // Reset to original data
    renderCharts();
    renderKPIs();
}

function exportChart(chartType) {
    // This would implement chart export functionality
    console.log('Exporting chart:', chartType);
    alert('Funcionalidade de exportação será implementada em breve!');
}

// Utility functions
function uploadFile() {
    fileInput.click();
}

// Export functions
function exportToCSV() {
    if (!currentData) return;
    
    const csvContent = convertToCSV(currentData.raw_data);
    downloadCSV(csvContent, 'dados_ads.csv');
}

function convertToCSV(data) {
    if (!data || data.length === 0) return '';
    
    const headers = Object.keys(data[0]);
    const csvRows = [headers.join(',')];
    
    data.forEach(row => {
        const values = headers.map(header => {
            const value = row[header];
            return typeof value === 'string' && value.includes(',') 
                ? `"${value}"` 
                : value;
        });
        csvRows.push(values.join(','));
    });
    
    return csvRows.join('\n');
}

function downloadCSV(content, filename) {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

// Auto upload functionality
function initializeAutoUpload() {
    const autoUploadBtn = document.getElementById('autoUploadBtn');
    
    if (autoUploadBtn) {
        autoUploadBtn.addEventListener('click', handleAutoUpload);
    }
}

async function handleAutoUpload() {
    const autoUploadBtn = document.getElementById('autoUploadBtn');
    const originalText = autoUploadBtn.innerHTML;
    
    try {
        // Show loading state
        autoUploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Carregando...';
        autoUploadBtn.disabled = true;
        
        // Make request to auto-upload endpoint
        const response = await fetch('/auto-upload', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        console.log('Response from auto-upload:', result);
        
        if (result.success) {
            // Process the data
            currentData = result.data;
            filteredData = currentData;
            
            // Show dashboard (this will render everything)
            showDashboard();
            
            // Show success message
            showNotification(result.message || 'Planilha carregada automaticamente do Google Drive!', 'success');
        } else {
            showNotification(result.error || 'Erro ao carregar planilha automaticamente', 'error');
        }
        
    } catch (error) {
        console.error('Erro no upload automático:', error);
        showNotification('Erro de conexão ao carregar planilha automaticamente', 'error');
    } finally {
        // Restore button state
        autoUploadBtn.innerHTML = originalText;
        autoUploadBtn.disabled = false;
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Show notification
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Hide after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => document.body.removeChild(notification), 300);
    }, 5000);
}
