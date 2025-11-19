// Global variables
let currentData = null;
let currentLeadsData = null;
let temporalChart = null;
let creativesChart = null;
let distributionChart = null;
let temporalDetailedChart = null;
let costsChart = null;
let conversionChart = null;
let campaignsChart = null;
let filteredData = null;
let leadSourceChart = null;
let filteredLeadsData = null;

// DOM Elements
const uploadSection = document.getElementById('uploadSection');
const loadingSection = document.getElementById('loadingSection');
const dashboardSection = document.getElementById('dashboardSection');
const leadsDashboardSection = document.getElementById('leadsDashboardSection');
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const leadsFileInput = document.getElementById('leadsFileInput');
const kpisGrid = document.getElementById('kpisGrid');
const dataTable = document.getElementById('dataTable');
const tableHead = document.getElementById('tableHead');
const tableBody = document.getElementById('tableBody');
const leadsKpisGrid = document.getElementById('leadsKpisGrid');
const leadsTableHead = document.getElementById('leadsTableHead');
const leadsTableBody = document.getElementById('leadsTableBody');
const leadsRecentHead = document.getElementById('leadsRecentHead');
const leadsRecentBody = document.getElementById('leadsRecentBody');
const leadSourceList = document.getElementById('leadSourceList');
const leadOwnerList = document.getElementById('leadOwnerList');
const leadSearchInput = document.getElementById('leadSearchInput');
const leadRowsSelect = document.getElementById('leadRowsSelect');
let autoLeadsUploadBtn = document.getElementById('autoLeadsUploadBtn');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    if (!autoLeadsUploadBtn) {
        const buttonsContainer = document.querySelector('.auto-upload-buttons');
        if (buttonsContainer) {
            const leadsBtn = document.createElement('button');
            leadsBtn.className = 'btn btn-secondary';
            leadsBtn.id = 'autoLeadsUploadBtn';
            leadsBtn.innerHTML = '<i class="fas fa-users"></i> Carregar Leads';
            buttonsContainer.appendChild(leadsBtn);
            autoLeadsUploadBtn = leadsBtn;
        }
    }
    
    initializeCharts();
    initializeFilters();
    initializeAutoUpload();
    initializeLeadsUpload();
    initializeLeadControls();
    initializeSultsData();
});

function showLoading() {
    uploadSection.style.display = 'none';
    dashboardSection.style.display = 'none';
    if (leadsDashboardSection) {
        leadsDashboardSection.style.display = 'none';
    }
    loadingSection.style.display = 'block';
}

function showUpload() {
    uploadSection.style.display = 'block';
    dashboardSection.style.display = 'none';
    if (leadsDashboardSection) {
        leadsDashboardSection.style.display = 'none';
    }
    loadingSection.style.display = 'none';
    
    // Hide back button when on upload screen
    const backBtn = document.getElementById('backToStartBtn');
    if (backBtn) {
        backBtn.style.display = 'none';
    }
}

function showDashboard() {
    uploadSection.style.display = 'none';
    loadingSection.style.display = 'none';
    dashboardSection.style.display = 'block';
    if (leadsDashboardSection) {
        leadsDashboardSection.style.display = 'none';
    }
    
    filteredData = currentData; // Initialize filtered data
    populateFilters();
    renderKPIs();
    renderCharts();
    renderTable();
    
    // Add fade-in animation
    dashboardSection.classList.add('fade-in');
    
    // Show back button when viewing dashboard
    const backBtn = document.getElementById('backToStartBtn');
    if (backBtn) {
        backBtn.style.display = 'block';
    }
}

function showLeadsDashboard() {
    if (!currentLeadsData || !leadsDashboardSection) return;
    
    uploadSection.style.display = 'none';
    dashboardSection.style.display = 'none';
    loadingSection.style.display = 'none';
    leadsDashboardSection.style.display = 'block';
    
    filteredLeadsData = currentLeadsData;
    renderLeadsDashboard();
    
    leadsDashboardSection.classList.add('fade-in');
    
    const backBtn = document.getElementById('backToStartBtn');
    if (backBtn) {
        backBtn.style.display = 'block';
    }
}

function backToStart() {
    currentData = null;
    filteredData = null;
    currentLeadsData = null;
    filteredLeadsData = null;
    showUpload();
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

    // Date range - calculate actual number of unique dates in raw_data
    let dateRange = 0;
    if (filteredData.raw_data && filteredData.raw_data.length > 0) {
        const dateCol = filteredData.date_column || 'Data';
        const uniqueDates = new Set();
        filteredData.raw_data.forEach(row => {
            const date = row[dateCol] || row['Data_Processada'];
            if (date) uniqueDates.add(date);
        });
        dateRange = uniqueDates.size;
    } else if (filteredData.summary && filteredData.summary.temporal) {
        dateRange = filteredData.summary.temporal.length;
    }
    
    if (dateRange > 0) {
        const dateCard = createKPICard(
            'Período Analisado',
            dateRange + ' dias',
            'fas fa-calendar',
            '#6B7280'
        );
        kpisGrid.appendChild(dateCard);
    }

    if (kpis.tag_leads !== undefined) {
        const tagLeadsCard = createKPICard(
            'Leads (tag LEAD)',
            kpis.tag_leads.toLocaleString(),
            'fas fa-user-plus',
            '#0EA5E9'
        );
        kpisGrid.appendChild(tagLeadsCard);
    }

    if (kpis.tag_mqls !== undefined) {
        const tagMQLsCard = createKPICard(
            'MQLs (tag MQL)',
            kpis.tag_mqls.toLocaleString(),
            'fas fa-user-check',
            '#10B981'
        );
        kpisGrid.appendChild(tagMQLsCard);
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

function renderLeadsDashboard() {
    if (!filteredLeadsData) return;
    
    renderLeadsKPIs();
    renderLeadCharts();
    renderLeadDistributions();
    renderLeadRecentTable();
    renderLeadsByPhase();
    renderLeadsTable();
}

function renderLeadsKPIs() {
    if (!leadsKpisGrid || !filteredLeadsData) return;
    
    const kpis = filteredLeadsData.kpis || {};
    leadsKpisGrid.innerHTML = '';
    
    if (kpis.total_leads !== undefined) {
        leadsKpisGrid.appendChild(
            createKPICard(
                'Total de Leads',
                kpis.total_leads.toLocaleString(),
                'fas fa-users',
                '#10B981'
            )
        );
    }
    
    if (kpis.leads_last_30_days !== undefined) {
        leadsKpisGrid.appendChild(
            createKPICard(
                'Entradas (30 dias)',
                kpis.leads_last_30_days.toLocaleString(),
                'fas fa-calendar-plus',
                '#3B82F6'
            )
        );
    }
    
    if (kpis.leads_active !== undefined) {
        leadsKpisGrid.appendChild(
            createKPICard(
                'Leads em Aberto',
                kpis.leads_active.toLocaleString(),
                'fas fa-hourglass-half',
                '#F97316'
            )
        );
    }
    
    if (kpis.leads_won !== undefined) {
        leadsKpisGrid.appendChild(
            createKPICard(
                'Leads Convertidos',
                kpis.leads_won.toLocaleString(),
                'fas fa-trophy',
                '#8B5CF6'
            )
        );
    }
    
    if (kpis.leads_lost !== undefined) {
        leadsKpisGrid.appendChild(
            createKPICard(
                'Leads Perdidos',
                kpis.leads_lost.toLocaleString(),
                'fas fa-user-slash',
                '#EF4444'
            )
        );
    }
    
    if (kpis.tag_mqls !== undefined && kpis.tag_mqls > 0) {
        leadsKpisGrid.appendChild(
            createKPICard(
                'MQLs (Etiqueta MQL)',
                kpis.tag_mqls.toLocaleString(),
                'fas fa-user-check',
                '#10B981'
            )
        );
    }
    
    if (kpis.mql_to_lead_rate !== undefined) {
        leadsKpisGrid.appendChild(
            createKPICard(
                'Taxa de MQL para Lead',
                `${kpis.mql_to_lead_rate.toFixed(1)}%`,
                'fas fa-percentage',
                '#001c54'
            )
        );
    }
    
    if (kpis.tag_leads !== undefined) {
        leadsKpisGrid.appendChild(
            createKPICard(
                'Total de Leads',
                kpis.tag_leads.toLocaleString(),
                'fas fa-users',
                '#0EA5E9'
            )
        );
    }
    
}

function renderLeadCharts() {
    if (!filteredLeadsData) return;
    
    const distributions = filteredLeadsData.distributions || {};
    
    // Renderizar apenas gráfico de origem dos leads
    if (leadSourceChart) {
        const sourceData = distributions.source || [];
        leadSourceChart.data.labels = sourceData.map(item => item.label);
        leadSourceChart.data.datasets[0].data = sourceData.map(item => item.value);
        leadSourceChart.update();
    }
}

function renderLeadsByPhaseChart(data) {
    // Criar ou atualizar gráfico de leads por fase
    const canvasId = 'leadsByPhaseChart';
    let canvas = document.getElementById(canvasId);
    
    if (!canvas) {
        // Criar canvas se não existir
        const chartContainer = document.querySelector('.lead-charts-container') || document.getElementById('leadChartsSection');
        if (chartContainer) {
            canvas = document.createElement('canvas');
            canvas.id = canvasId;
            canvas.style.maxHeight = '400px';
            const chartDiv = document.createElement('div');
            chartDiv.className = 'chart-container';
            chartDiv.innerHTML = '<h3>Leads por Fase</h3>';
            chartDiv.appendChild(canvas);
            chartContainer.appendChild(chartDiv);
        } else {
            return;
        }
    }
    
    const ctx = canvas.getContext('2d');
    
    // Destruir gráfico anterior se existir
    if (window.leadsByPhaseChart) {
        window.leadsByPhaseChart.destroy();
    }
    
    // Ordem customizada das fases
    const ordemFases = {
        'lead': 1,
        'mql': 2,
        'conexao': 3,
        'conexão': 3,
        'pre-call agendada': 4,
        'pre call agendada': 4,
        'pre-call realizada': 5,
        'pre call realizada': 5,
        'apresentação modelo agendada': 6,
        'apresentacao modelo agendada': 6,
        'apresentação modelo realizada': 7,
        'apresentacao modelo realizada': 7,
        'apresentação financeira agendada': 8,
        'apresentacao financeira agendada': 8,
        'reunião financeira realizada': 9,
        'reuniao financeira realizada': 9,
        'reunião fundador agendada': 10,
        'reuniao fundador agendada': 10,
        'aguardando decisão': 11,
        'aguardando decisao': 11,
        'contrato franquia': 12
    };
    
    const estatisticas = filteredLeadsData?.estatisticas || {};
    const ordem = estatisticas.leads_por_fase_ordem || {};
    const sorted = Object.entries(data).sort((a, b) => {
        const faseA = a[0].toLowerCase().trim();
        const faseB = b[0].toLowerCase().trim();
        
        let ordemA = ordem[faseA] || 9999;
        let ordemB = ordem[faseB] || 9999;
        
        // Se não encontrou na ordem do backend, procurar no mapeamento local
        if (ordemA === 9999) {
            for (const [key, val] of Object.entries(ordemFases)) {
                if (faseA.includes(key)) {
                    ordemA = val;
                    break;
                }
            }
        }
        
        if (ordemB === 9999) {
            for (const [key, val] of Object.entries(ordemFases)) {
                if (faseB.includes(key)) {
                    ordemB = val;
                    break;
                }
            }
        }
        
        return ordemA - ordemB;
    });
    
    const labels = sorted.map(([fase]) => fase);
    const values = sorted.map(([, count]) => count);
    
    window.leadsByPhaseChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Leads',
                data: values,
                backgroundColor: 'rgba(0, 28, 84, 0.8)',
                borderColor: '#001c54',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });
}

function renderLeadsByCategoryChart(data) {
    const canvasId = 'leadsByCategoryChart';
    let canvas = document.getElementById(canvasId);
    
    if (!canvas) {
        const chartContainer = document.querySelector('.lead-charts-container') || document.getElementById('leadChartsSection');
        if (chartContainer) {
            canvas = document.createElement('canvas');
            canvas.id = canvasId;
            canvas.style.maxHeight = '400px';
            const chartDiv = document.createElement('div');
            chartDiv.className = 'chart-container';
            chartDiv.innerHTML = '<h3>Leads por Categoria</h3>';
            chartDiv.appendChild(canvas);
            chartContainer.appendChild(chartDiv);
        } else {
            return;
        }
    }
    
    const ctx = canvas.getContext('2d');
    
    if (window.leadsByCategoryChart) {
        window.leadsByCategoryChart.destroy();
    }
    
    const labels = Object.keys(data);
    const values = Object.values(data);
    
    window.leadsByCategoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    '#001c54',
                    '#edb125',
                    '#de5e36',
                    '#2374b9',
                    '#10B981',
                    '#8B5CF6'
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
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
}


function renderLeadDistributions() {
    const distributions = filteredLeadsData?.distributions || {};
    const estatisticas = filteredLeadsData?.estatisticas || {};
    
    // Adicionar distribuições de fase e categoria se disponíveis
    if (estatisticas && estatisticas.leads_por_fase && typeof estatisticas.leads_por_fase === 'object') {
        const faseList = document.getElementById('leadFaseList');
        if (faseList) {
            faseList.innerHTML = '';
            // Ordem customizada das fases
            const ordemFases = {
                'lead': 1,
                'mql': 2,
                'conexao': 3,
                'conexão': 3,
                'pre-call agendada': 4,
                'pre call agendada': 4,
                'pre-call realizada': 5,
                'pre call realizada': 5,
                'apresentação modelo agendada': 6,
                'apresentacao modelo agendada': 6,
                'apresentação modelo realizada': 7,
                'apresentacao modelo realizada': 7,
                'apresentação financeira agendada': 8,
                'apresentacao financeira agendada': 8,
                'reunião financeira realizada': 9,
                'reuniao financeira realizada': 9,
                'reunião fundador agendada': 10,
                'reuniao fundador agendada': 10,
                'aguardando decisão': 11,
                'aguardando decisao': 11,
                'contrato franquia': 12
            };
            
            const ordem = estatisticas.leads_por_fase_ordem || {};
            const sorted = Object.entries(estatisticas.leads_por_fase).sort((a, b) => {
                const faseA = a[0].toLowerCase().trim();
                const faseB = b[0].toLowerCase().trim();
                
                let ordemA = ordem[faseA] || 9999;
                let ordemB = ordem[faseB] || 9999;
                
                // Se não encontrou na ordem do backend, procurar no mapeamento local
                if (ordemA === 9999) {
                    for (const [key, val] of Object.entries(ordemFases)) {
                        if (faseA.includes(key)) {
                            ordemA = val;
                            break;
                        }
                    }
                }
                
                if (ordemB === 9999) {
                    for (const [key, val] of Object.entries(ordemFases)) {
                        if (faseB.includes(key)) {
                            ordemB = val;
                            break;
                        }
                    }
                }
                
                return ordemA - ordemB;
            });
            sorted.forEach(([fase, count]) => {
                const item = document.createElement('div');
                item.className = 'distribution-item';
                item.innerHTML = `
                    <span class="distribution-label">${fase}</span>
                    <span class="distribution-value">${count}</span>
                `;
                faseList.appendChild(item);
            });
        }
    }
    
    populateDistributionList(leadSourceList, distributions.source, 'Leads');
    populateDistributionList(leadOwnerList, distributions.owner, 'Leads');
}

function populateDistributionList(container, items, label) {
    if (!container) return;
    
    if (!items || items.length === 0) {
        container.innerHTML = '<p class="empty-state">Nenhum dado disponível</p>';
        return;
    }
    
    container.innerHTML = '';
    
    items.slice(0, 7).forEach(item => {
        const row = document.createElement('div');
        row.className = 'distribution-item';
        row.innerHTML = `
            <span class="distribution-label">${item.label || 'N/A'}</span>
            <span class="distribution-value">${(item.value || 0).toLocaleString()} ${label}</span>
        `;
        container.appendChild(row);
    });
}

function renderLeadRecentTable() {
    if (!leadsRecentHead || !leadsRecentBody) return;
    
    const recentData = filteredLeadsData?.recent_leads || [];
    
    leadsRecentHead.innerHTML = '';
    leadsRecentBody.innerHTML = '';
    
    if (!recentData.length) {
        leadsRecentBody.innerHTML = '<tr><td>Nenhum dado recente disponível</td></tr>';
        return;
    }
    
    const headers = Object.keys(recentData[0]);
    const headerRow = document.createElement('tr');
    headers.forEach(header => {
        const th = document.createElement('th');
        th.textContent = header;
        headerRow.appendChild(th);
    });
    leadsRecentHead.appendChild(headerRow);
    
    recentData.forEach(row => {
        const tr = document.createElement('tr');
        headers.forEach(header => {
            const td = document.createElement('td');
            const value = row[header];
            td.textContent = value !== null && value !== undefined ? value : '';
            tr.appendChild(td);
        });
        leadsRecentBody.appendChild(tr);
    });
}

function renderLeadsTable() {
    if (!leadsTableHead || !leadsTableBody || !filteredLeadsData) return;
    
    // Para dados da SULTS, usar leads diretamente
    const leads = filteredLeadsData.leads || [];
    
    leadsTableHead.innerHTML = '';
    leadsTableBody.innerHTML = '';
    
    if (!leads.length) {
        leadsTableBody.innerHTML = '<tr><td colspan="9">Nenhum lead encontrado</td></tr>';
        return;
    }
    
    // Criar cabeçalho da tabela
    const headerRow = document.createElement('tr');
    const headers = ['Nome', 'Email', 'Telefone', 'Status', 'Fase', 'Categoria', 'Responsável', 'Unidade', 'Data'];
    headers.forEach(header => {
        const th = document.createElement('th');
        th.textContent = header;
        headerRow.appendChild(th);
    });
    leadsTableHead.appendChild(headerRow);
    
    // Criar linhas da tabela
    leads.forEach(lead => {
        const tr = document.createElement('tr');
        
        // Nome
        const tdNome = document.createElement('td');
        tdNome.textContent = lead.nome || 'Sem nome';
        tr.appendChild(tdNome);
        
        // Email
        const tdEmail = document.createElement('td');
        tdEmail.textContent = lead.email || '-';
        tr.appendChild(tdEmail);
        
        // Telefone
        const tdTelefone = document.createElement('td');
        tdTelefone.textContent = lead.telefone || '-';
        tr.appendChild(tdTelefone);
        
        // Status
        const tdStatus = document.createElement('td');
        const statusBadge = document.createElement('span');
        statusBadge.className = 'status-badge';
        const status = lead.status || 'Sem status';
        statusBadge.textContent = status;
        if (status === 'aberto' || status === 'Aberto') {
            statusBadge.style.backgroundColor = '#F97316';
        } else if (status === 'ganho' || status === 'Ganho') {
            statusBadge.style.backgroundColor = '#10B981';
        } else if (status === 'perdido' || status === 'Perdido') {
            statusBadge.style.backgroundColor = '#EF4444';
        }
        tdStatus.appendChild(statusBadge);
        tr.appendChild(tdStatus);
        
        // Fase
        const tdFase = document.createElement('td');
        tdFase.textContent = lead.fase || lead.categoria || '-';
        tr.appendChild(tdFase);
        
        // Categoria
        const tdCategoria = document.createElement('td');
        tdCategoria.textContent = lead.categoria || '-';
        tr.appendChild(tdCategoria);
        
        // Responsável
        const tdResponsavel = document.createElement('td');
        tdResponsavel.textContent = lead.responsavel || '-';
        tr.appendChild(tdResponsavel);
        
        // Unidade
        const tdUnidade = document.createElement('td');
        tdUnidade.textContent = lead.unidade || '-';
        tr.appendChild(tdUnidade);
        
        // Data
        const tdData = document.createElement('td');
        const dataStr = lead.data || '';
        tdData.textContent = dataStr ? new Date(dataStr).toLocaleDateString('pt-BR') : '-';
        tr.appendChild(tdData);
        
        leadsTableBody.appendChild(tr);
    });
    
    filterLeadsTable();
}

function renderLeadsByPhase() {
    const container = document.getElementById('leadsByPhaseContainer');
    if (!container || !filteredLeadsData) return;
    
    const leads = filteredLeadsData.leads || [];
    
    // Organizar leads por fase
    const leadsByPhase = {};
    leads.forEach(lead => {
        const fase = lead.fase || 'Sem fase';
        if (!leadsByPhase[fase]) {
            leadsByPhase[fase] = [];
        }
        leadsByPhase[fase].push(lead);
    });
    
    container.innerHTML = '';
    
    // Ordem customizada das fases
    const ordemFases = {
        'lead': 1,
        'mql': 2,
        'conexao': 3,
        'conexão': 3,
        'pre-call agendada': 4,
        'pre call agendada': 4,
        'pre-call realizada': 5,
        'pre call realizada': 5,
        'apresentação modelo agendada': 6,
        'apresentacao modelo agendada': 6,
        'apresentação modelo realizada': 7,
        'apresentacao modelo realizada': 7,
        'apresentação financeira agendada': 8,
        'apresentacao financeira agendada': 8,
        'reunião financeira realizada': 9,
        'reuniao financeira realizada': 9,
        'reunião fundador agendada': 10,
        'reuniao fundador agendada': 10,
        'aguardando decisão': 11,
        'aguardando decisao': 11,
        'contrato franquia': 12
    };
    
    const estatisticas = filteredLeadsData?.estatisticas || {};
    const ordem = estatisticas.leads_por_fase_ordem || {};
    const sortedPhases = Object.entries(leadsByPhase).sort((a, b) => {
        const faseA = a[0].toLowerCase().trim();
        const faseB = b[0].toLowerCase().trim();
        
        let ordemA = ordem[faseA] || 9999;
        let ordemB = ordem[faseB] || 9999;
        
        // Se não encontrou na ordem do backend, procurar no mapeamento local
        if (ordemA === 9999) {
            for (const [key, val] of Object.entries(ordemFases)) {
                if (faseA.includes(key)) {
                    ordemA = val;
                    break;
                }
            }
        }
        
        if (ordemB === 9999) {
            for (const [key, val] of Object.entries(ordemFases)) {
                if (faseB.includes(key)) {
                    ordemB = val;
                    break;
                }
            }
        }
        
        return ordemA - ordemB;
    });
    
    sortedPhases.forEach(([fase, faseLeads]) => {
        const phaseCard = document.createElement('div');
        phaseCard.className = 'phase-card';
        
        const phaseHeader = document.createElement('div');
        phaseHeader.className = 'phase-header';
        phaseHeader.innerHTML = `
            <div class="phase-title">
                <i class="fas fa-chevron-down phase-icon"></i>
                <h3>${fase}</h3>
                <span class="phase-count">${faseLeads.length} lead${faseLeads.length !== 1 ? 's' : ''}</span>
            </div>
        `;
        
        const phaseContent = document.createElement('div');
        phaseContent.className = 'phase-content';
        phaseContent.style.display = 'none';
        
        const leadsTable = document.createElement('table');
        leadsTable.className = 'phase-leads-table';
        leadsTable.innerHTML = `
            <thead>
                <tr>
                    <th>Nome</th>
                    <th>Status</th>
                    <th>Categoria</th>
                    <th>Responsável</th>
                    <th>Unidade</th>
                    <th>Data</th>
                </tr>
            </thead>
            <tbody>
                ${faseLeads.map(lead => `
                    <tr>
                        <td>${lead.nome || 'Sem nome'}</td>
                        <td>
                            <span class="status-badge" style="background-color: ${
                                lead.status === 'aberto' ? '#F97316' : 
                                lead.status === 'ganho' ? '#10B981' : '#EF4444'
                            }">
                                ${lead.status || 'Sem status'}
                            </span>
                        </td>
                        <td>${lead.categoria || '-'}</td>
                        <td>${lead.responsavel || '-'}</td>
                        <td>${lead.unidade || '-'}</td>
                        <td>${lead.data ? new Date(lead.data).toLocaleDateString('pt-BR') : '-'}</td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        
        phaseContent.appendChild(leadsTable);
        
        phaseHeader.addEventListener('click', () => {
            const isExpanded = phaseContent.style.display !== 'none';
            phaseContent.style.display = isExpanded ? 'none' : 'block';
            const icon = phaseHeader.querySelector('.phase-icon');
            icon.classList.toggle('fa-chevron-down', isExpanded);
            icon.classList.toggle('fa-chevron-up', !isExpanded);
        });
        
        phaseCard.appendChild(phaseHeader);
        phaseCard.appendChild(phaseContent);
        container.appendChild(phaseCard);
    });
}

function filterLeadsTable() {
    if (!leadsTableBody) return;
    
    const searchTerm = (leadSearchInput?.value || '').toLowerCase();
    const maxRows = leadRowsSelect ? leadRowsSelect.value : 'all';
    const rows = leadsTableBody.querySelectorAll('tr');
    
    let visibleCount = 0;
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const isVisible = !searchTerm || text.includes(searchTerm);
        
        if (isVisible && (maxRows === 'all' || visibleCount < parseInt(maxRows, 10))) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
}

function exportLeadChart(chartType) {
    console.log('Exporting lead chart:', chartType);
    alert('Exportação de gráficos de leads estará disponível em breve!');
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

    const leadSourceCtx = document.getElementById('leadSourceChart');
    if (leadSourceCtx) {
        leadSourceChart = new Chart(leadSourceCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Leads',
                    data: [],
                    backgroundColor: 'rgba(0, 28, 84, 0.85)',
                    borderColor: '#001c54',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: {
                            color: '#E5E7EB'
                        },
                        ticks: {
                            color: '#6B7280'
                        }
                    },
                    y: {
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
    }

    const leadTimelineCtx = document.getElementById('leadTimelineChart');
    if (leadTimelineCtx) {
        leadTimelineChart = new Chart(leadTimelineCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Leads',
                    data: [],
                    borderColor: '#edb125',
                    backgroundColor: 'rgba(237, 177, 37, 0.15)',
                    borderWidth: 3,
                    tension: 0.35,
                    fill: true
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
    }
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
    console.log('Applying date filter:', dateFilter);
    
    // Create filtered data
    filteredData = JSON.parse(JSON.stringify(currentData)); // Deep copy
    
    // Apply date filter to raw_data
    if (dateFilter !== 'all' && filteredData.raw_data) {
        const dateCol = filteredData.date_column || 'Data';
        console.log('Date column:', dateCol);
        console.log('Raw data rows before filter:', filteredData.raw_data.length);
        
        // Helper function to normalize date format
        function normalizeDate(dateStr) {
            if (!dateStr) return '';
            
            // If already in DD/MM/YYYY format, return as is
            if (dateStr.match(/^\d{2}\/\d{2}\/\d{4}$/)) {
                return dateStr;
            }
            
            // If in YYYY-MM-DD format (with or without time)
            if (dateStr.match(/^\d{4}-\d{2}-\d{2}/)) {
                const parts = dateStr.split(' ')[0].split('-');
                return `${parts[2]}/${parts[1]}/${parts[0]}`;
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
        
        filteredData.raw_data = filteredData.raw_data.filter(row => {
            const rowDate = row[dateCol] || row['Data_Processada'] || '';
            const normalizedRowDate = normalizeDate(rowDate);
            return normalizedRowDate === dateFilter;
        });
        
        console.log('Raw data rows after filter:', filteredData.raw_data.length);
        
        // Recalculate KPIs based on filtered data
        filteredData.kpis = calculateKPIs(filteredData);
        filteredData.total_rows = filteredData.raw_data.length;
        console.log('Recalculated KPIs:', filteredData.kpis);
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

function calculateKPIs(data) {
    if (!data.raw_data || data.raw_data.length === 0) {
        return {
            total_leads: 0,
            total_mqls: 0,
            investimento_total: 0,
            custo_por_mql: 0
        };
    }
    
    const leadsCol = data.leads_columns?.lead;
    const mqlCol = data.leads_columns?.mql;
    const costCol = data.cost_columns?.total;
    
    let totalLeads = 0;
    let totalMQLs = 0;
    let totalCost = 0;
    
    data.raw_data.forEach(row => {
        // Sum leads
        if (leadsCol && row[leadsCol] !== undefined) {
            const leads = parseFloat(row[leadsCol]) || 0;
            totalLeads += leads;
        }
        
        // Sum MQLs
        if (mqlCol && row[mqlCol] !== undefined) {
            const mqls = parseFloat(row[mqlCol]) || 0;
            totalMQLs += mqls;
        }
        
        // Sum cost
        if (costCol && row[costCol] !== undefined) {
            const cost = parseFloat(row[costCol]) || 0;
            totalCost += cost;
        }
    });
    
    // Calculate Custo por MQL
    const custoMQL = totalMQLs > 0 ? totalCost / totalMQLs : 0;
    
    return {
        total_leads: Math.round(totalLeads),
        total_mqls: Math.round(totalMQLs),
        investimento_total: parseFloat(totalCost.toFixed(2)),
        custo_por_mql: parseFloat(custoMQL.toFixed(2))
    };
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
    const googleAdsUploadBtn = document.getElementById('googleAdsUploadBtn');
    
    if (autoUploadBtn) {
        autoUploadBtn.addEventListener('click', handleAutoUpload);
    }
    
    if (googleAdsUploadBtn) {
        googleAdsUploadBtn.addEventListener('click', handleGoogleAdsUpload);
    }
    
    if (autoLeadsUploadBtn) {
        autoLeadsUploadBtn.addEventListener('click', handleLeadsAutoUpload);
    }
}

function initializeLeadsUpload() {
    const leadsUploadBtn = document.getElementById('leadsUploadBtn');
    
    if (leadsUploadBtn && leadsFileInput) {
        leadsUploadBtn.addEventListener('click', () => leadsFileInput.click());
        leadsFileInput.addEventListener('change', handleLeadsFileUpload);
    }
}

function initializeLeadControls() {
    if (leadSearchInput) {
        leadSearchInput.addEventListener('input', filterLeadsTable);
    }
    
    if (leadRowsSelect) {
        leadRowsSelect.addEventListener('change', filterLeadsTable);
    }
}

function initializeSultsData() {
    const sultsDataBtn = document.getElementById('sultsDataBtn');
    if (sultsDataBtn) {
        sultsDataBtn.addEventListener('click', handleSultsDataLoad);
    }
}

async function handleSultsDataLoad() {
    showLoading();
    
    try {
        const response = await fetch('/api/sults/verificar-leads');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        console.log('Resposta da API SULTS:', result);
        
        if (result.success && result.data) {
            displaySultsData(result.data);
        } else {
            const errorMsg = result.error || result.message || 'Erro desconhecido';
            console.error('Erro na resposta:', errorMsg);
            alert('Erro ao carregar dados da SULTS: ' + errorMsg);
            showUpload();
        }
    } catch (error) {
        console.error('Erro ao buscar dados SULTS:', error);
        alert('Erro ao conectar com a API SULTS: ' + error.message + '. Verifique se o servidor está rodando na porta 5003.');
        showUpload();
    }
}

function displaySultsData(data) {
    console.log('Dados recebidos da SULTS:', data);
    
    // Criar estrutura de dados similar ao formato de leads
    const sultsLeads = {
        leads: {
            abertos: data.leads?.abertos?.dados || [],
            perdidos: data.leads?.perdidos?.dados || [],
            ganhos: data.leads?.ganhos?.dados || [],
            mql: data.leads?.mql?.dados || []
        },
        resumo: {
            total_leads: data.resumo?.total_leads || 0,
            abertos: data.leads?.abertos?.total || 0,
            perdidos: data.leads?.perdidos?.total || 0,
            ganhos: data.leads?.ganhos?.total || 0,
            mql: data.resumo?.leads_mql || data.leads?.mql?.total || 0
        },
        estatisticas: data.estatisticas || {
            leads_por_fase: {},
            leads_por_categoria: {},
            leads_por_responsavel: {},
            leads_por_unidade: {}
        }
    };
    
    // Garantir que todas as propriedades de estatisticas existem
    if (!sultsLeads.estatisticas.leads_por_fase) sultsLeads.estatisticas.leads_por_fase = {};
    if (!sultsLeads.estatisticas.leads_por_categoria) sultsLeads.estatisticas.leads_por_categoria = {};
    if (!sultsLeads.estatisticas.leads_por_responsavel) sultsLeads.estatisticas.leads_por_responsavel = {};
    if (!sultsLeads.estatisticas.leads_por_unidade) sultsLeads.estatisticas.leads_por_unidade = {};
    
    // Combinar todos os leads para exibição
    const allLeads = [
        ...(sultsLeads.leads.abertos || []),
        ...(sultsLeads.leads.perdidos || []),
        ...(sultsLeads.leads.ganhos || []),
        ...(sultsLeads.leads.mql || [])
    ];
    
    // Remover duplicatas baseado no ID
    const leadsMap = new Map();
    allLeads.forEach(lead => {
        if (lead.id && !leadsMap.has(lead.id)) {
            leadsMap.set(lead.id, lead);
        }
    });
    const uniqueLeads = Array.from(leadsMap.values());
    
    console.log('Total de leads processados:', uniqueLeads.length);
    console.log('Leads abertos:', sultsLeads.resumo.abertos);
    console.log('Leads perdidos:', sultsLeads.resumo.perdidos);
    console.log('Leads ganhos:', sultsLeads.resumo.ganhos);
    console.log('Leads MQL:', sultsLeads.resumo.mql);
    
    // Calcular taxa de MQL para Lead
    const totalLeads = sultsLeads.resumo.total_leads || uniqueLeads.length;
    const totalMQL = sultsLeads.resumo.mql || 0;
    const mqlToLeadRate = totalLeads > 0 ? (totalMQL / totalLeads) * 100 : 0;
    
    // Criar dados no formato esperado pelo dashboard
    currentLeadsData = {
        total_leads: totalLeads,
        tag_leads: totalLeads,
        tag_mqls: totalMQL,
        mql_to_lead_rate: mqlToLeadRate,
        leads: uniqueLeads.map(lead => ({
            nome: lead.nome || lead.name || 'Sem nome',
            email: lead.email || '',
            telefone: lead.telefone || lead.phone || '',
            status: lead.status || 'Sem status',
            origem: lead.origem || lead.source || 'SULTS',
            data: lead.data || lead.date || lead.data_criacao || lead.data_inicio || new Date().toISOString().split('T')[0],
            responsavel: lead.responsavel || '',
            unidade: lead.unidade || '',
            fase: lead.fase || '',
            categoria: lead.categoria || '',
            etapa: lead.etapa || '',
            funil: lead.funil || ''
        })),
        status_distribution: {
            'Abertos': sultsLeads.resumo.abertos,
            'Perdidos': sultsLeads.resumo.perdidos,
            'Ganhos': sultsLeads.resumo.ganhos,
            'MQL': totalMQL
        },
        kpis: {
            total_leads: totalLeads,
            leads_active: sultsLeads.resumo.abertos,
            leads_won: sultsLeads.resumo.ganhos,
            leads_lost: sultsLeads.resumo.perdidos,
            tag_leads: totalLeads,
            tag_mqls: totalMQL,
            mql_to_lead_rate: mqlToLeadRate
        },
        estatisticas: {
            leads_por_fase: sultsLeads.estatisticas.leads_por_fase || {},
            leads_por_fase_ordem: sultsLeads.estatisticas.leads_por_fase_ordem || {},
            leads_por_categoria: sultsLeads.estatisticas.leads_por_categoria || {},
            leads_por_responsavel: sultsLeads.estatisticas.leads_por_responsavel || {},
            leads_por_unidade: sultsLeads.estatisticas.leads_por_unidade || {}
        },
        source: 'SULTS API',
        timestamp: new Date().toISOString()
    };
    
    filteredLeadsData = currentLeadsData;
    
    console.log('Dados finais preparados:', currentLeadsData);
    
    // Exibir no dashboard de leads
    showLeadsDashboard();
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

async function handleGoogleAdsUpload() {
    const googleAdsUploadBtn = document.getElementById('googleAdsUploadBtn');
    const originalText = googleAdsUploadBtn.innerHTML;
    
    try {
        // Show loading state
        googleAdsUploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Carregando...';
        googleAdsUploadBtn.disabled = true;
        
        // Make request to google-ads-upload endpoint
        const response = await fetch('/google-ads-upload', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        console.log('Response from google-ads-upload:', result);
        
        if (result.success) {
            // Process the data
            currentData = result.data;
            filteredData = currentData;
            
            // Show dashboard
            showDashboard();
            
            // Show success message
            showNotification(result.message || 'Planilha do Google Ads carregada automaticamente!', 'success');
        } else {
            showNotification(result.error || 'Erro ao carregar planilha do Google Ads', 'error');
        }
        
    } catch (error) {
        console.error('Erro no upload do Google Ads:', error);
        showNotification('Erro de conexão ao carregar planilha do Google Ads', 'error');
    } finally {
        // Restore button state
        googleAdsUploadBtn.innerHTML = originalText;
        googleAdsUploadBtn.disabled = false;
    }
}

async function handleLeadsAutoUpload() {
    if (!autoLeadsUploadBtn) return;
    const originalText = autoLeadsUploadBtn.innerHTML;
    
    try {
        autoLeadsUploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Carregando...';
        autoLeadsUploadBtn.disabled = true;
        
        const response = await fetch('/auto-upload-leads', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        console.log('Response from auto-upload-leads:', result);
        
        if (result.success) {
            currentLeadsData = result.data;
            filteredLeadsData = currentLeadsData;
            showLeadsDashboard();
            showNotification(result.message || 'Leads carregados automaticamente do Google Drive!', 'success');
        } else {
            showNotification(result.error || 'Erro ao carregar leads automaticamente', 'error');
        }
    } catch (error) {
        console.error('Erro no auto upload de leads:', error);
        showNotification('Erro de conexão ao carregar leads automaticamente', 'error');
    } finally {
        autoLeadsUploadBtn.innerHTML = originalText;
        autoLeadsUploadBtn.disabled = false;
    }
}

async function handleLeadsFileUpload(event) {
    const files = event.target.files;
    if (!files || !files.length) return;
    
    const file = files[0];
    showLoading();
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/upload-leads', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        console.log('Response from leads upload:', result);
        
        if (result.success) {
            currentLeadsData = result.data;
            filteredLeadsData = currentLeadsData;
            showLeadsDashboard();
            showNotification(result.message || 'Dashboard de leads atualizado com sucesso!', 'success');
        } else {
            showUpload();
            showNotification(result.error || 'Erro ao processar planilha de leads', 'error');
        }
    } catch (error) {
        console.error('Erro no upload de leads:', error);
        showUpload();
        showNotification('Erro de conexão ao enviar planilha de leads', 'error');
    } finally {
        if (leadsFileInput) {
            leadsFileInput.value = '';
        }
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
