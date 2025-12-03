// ============================================
// MELHORIAS IMPLEMENTADAS - FUNCIONALIDADES AVANÇADAS
// ============================================

// ============================================
// MELHORIA 2: FILTROS AVANÇADOS
// ============================================
function initializeAdvancedFilters() {
    const dateRangeStart = document.getElementById('dateRangeStart');
    const dateRangeEnd = document.getElementById('dateRangeEnd');
    
    if (dateRangeStart && dateRangeEnd) {
        dateRangeStart.addEventListener('change', applyDateRangeFilter);
        dateRangeEnd.addEventListener('change', applyDateRangeFilter);
    }
}

function applyDateRangeFilter() {
    const startDate = document.getElementById('dateRangeStart')?.value;
    const endDate = document.getElementById('dateRangeEnd')?.value;
    
    if (!currentData || !currentData.raw_data) return;
    
    if (!startDate && !endDate) {
        filteredData = currentData;
        renderCharts();
        renderKPIs();
        return;
    }
    
    const dateCol = currentData.date_column;
    if (!dateCol) return;
    
    filteredData = {
        ...currentData,
        raw_data: currentData.raw_data.filter(row => {
            const rowDate = row[dateCol];
            if (!rowDate) return false;
            
            const date = new Date(rowDate);
            if (isNaN(date.getTime())) return false;
            
            if (startDate && date < new Date(startDate)) return false;
            if (endDate && date > new Date(endDate)) return false;
            
            return true;
        })
    };
    
    renderCharts();
    renderKPIs();
}

// ============================================
// MELHORIA 3: COMPARAÇÃO TEMPORAL
// ============================================
function renderTemporalComparison() {
    if (!currentData || !currentData.summary || !currentData.summary.temporal) return;
    
    const temporal = currentData.summary.temporal;
    if (temporal.length < 2) return;
    
    // Comparar mês atual vs anterior
    const currentMonth = temporal[temporal.length - 1];
    const previousMonth = temporal[temporal.length - 2];
    
    const comparison = {
        leads: {
            current: currentMonth.Criativos || 0,
            previous: previousMonth.Criativos || 0,
            change: ((currentMonth.Criativos || 0) - (previousMonth.Criativos || 0)) / (previousMonth.Criativos || 1) * 100
        }
    };
    
    // Criar card de comparação
    const comparisonSection = document.getElementById('comparisonSection');
    if (comparisonSection) {
        comparisonSection.innerHTML = `
            <div class="comparison-cards">
                <div class="comparison-card ${comparison.leads.change >= 0 ? 'positive' : 'negative'}">
                    <h4>Criativos</h4>
                    <div class="comparison-value">${comparison.leads.current}</div>
                    <p class="comparison-label">
                        ${comparison.leads.change >= 0 ? '+' : ''}${comparison.leads.change.toFixed(1)}% vs mês anterior
                    </p>
                </div>
            </div>
        `;
    }
}

// ============================================
// MELHORIA 4: RESPONSIVIDADE MOBILE
// ============================================
function initializeMobileOptimizations() {
    // Detectar mobile
    const isMobile = window.innerWidth < 768;
    
    if (isMobile) {
        // Otimizar gráficos para mobile
        document.querySelectorAll('canvas').forEach(canvas => {
            canvas.style.maxWidth = '100%';
            canvas.style.height = 'auto';
        });
        
        // Ajustar tabelas
        document.querySelectorAll('.data-table').forEach(table => {
            table.classList.add('mobile-table');
        });
    }
    
    // Ajustar ao redimensionar
    window.addEventListener('resize', () => {
        const isMobileNow = window.innerWidth < 768;
        if (isMobileNow !== isMobile) {
            location.reload(); // Recarregar para aplicar mudanças
        }
    });
}

// ============================================
// MELHORIA 5: ACESSIBILIDADE
// ============================================
function initializeAccessibility() {
    // Navegação por teclado
    document.addEventListener('keydown', (e) => {
        // ESC fecha modais
        if (e.key === 'Escape') {
            const modals = document.querySelectorAll('.modal');
            modals.forEach(modal => modal.remove());
        }
        
        // Ctrl/Cmd + K para busca
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('searchInput') || document.getElementById('leadSearchInput');
            if (searchInput) {
                searchInput.focus();
            }
        }
    });
    
    // ARIA labels para elementos interativos
    document.querySelectorAll('button').forEach(btn => {
        if (!btn.getAttribute('aria-label') && btn.textContent.trim()) {
            btn.setAttribute('aria-label', btn.textContent.trim());
        }
    });
    
    // Skip to main content
    const skipLink = document.createElement('a');
    skipLink.href = '#main-content';
    skipLink.className = 'skip-link';
    skipLink.textContent = 'Pular para conteúdo principal';
    skipLink.style.cssText = 'position: absolute; left: -9999px; z-index: 999;';
    skipLink.addEventListener('focus', () => {
        skipLink.style.left = '10px';
        skipLink.style.top = '10px';
    });
    skipLink.addEventListener('blur', () => {
        skipLink.style.left = '-9999px';
    });
    document.body.insertBefore(skipLink, document.body.firstChild);
}

// ============================================
// MELHORIA 6: CACHE INTELIGENTE (localStorage)
// ============================================
const CacheManager = {
    set: function(key, data, ttl = 300000) { // 5 minutos padrão
        const item = {
            data: data,
            timestamp: Date.now(),
            ttl: ttl
        };
        try {
            localStorage.setItem(`cache_${key}`, JSON.stringify(item));
        } catch (e) {
            console.warn('LocalStorage não disponível:', e);
        }
    },
    
    get: function(key) {
        try {
            const item = localStorage.getItem(`cache_${key}`);
            if (!item) return null;
            
            const parsed = JSON.parse(item);
            const now = Date.now();
            
            if (now - parsed.timestamp > parsed.ttl) {
                localStorage.removeItem(`cache_${key}`);
                return null;
            }
            
            return parsed.data;
        } catch (e) {
            return null;
        }
    },
    
    clear: function(key) {
        try {
            if (key) {
                localStorage.removeItem(`cache_${key}`);
            } else {
                Object.keys(localStorage).forEach(k => {
                    if (k.startsWith('cache_')) {
                        localStorage.removeItem(k);
                    }
                });
            }
        } catch (e) {
            console.warn('Erro ao limpar cache:', e);
        }
    }
};

// ============================================
// MELHORIA 7: LAZY LOADING
// ============================================
function initializeLazyLoading() {
    // Intersection Observer para carregar gráficos sob demanda
    const observerOptions = {
        root: null,
        rootMargin: '50px',
        threshold: 0.1
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const chartContainer = entry.target;
                const chartId = chartContainer.querySelector('canvas')?.id;
                
                if (chartId && !window[`${chartId}Loaded`]) {
                    // Carregar gráfico
                    window[`${chartId}Loaded`] = true;
                    // Os gráficos já são renderizados, apenas marcamos como carregados
                }
            }
        });
    }, observerOptions);
    
    // Observar containers de gráficos
    document.querySelectorAll('.chart-content').forEach(container => {
        observer.observe(container);
    });
}

// ============================================
// MELHORIA 8: NOTIFICAÇÕES MELHORADAS
// ============================================
function showAdvancedNotification(message, type = 'info', duration = 5000, actions = []) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type} show`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle',
        warning: 'fa-exclamation-triangle'
    };
    
    let actionsHTML = '';
    if (actions.length > 0) {
        actionsHTML = '<div class="notification-actions">' +
            actions.map(action => 
                `<button class="btn btn-sm" onclick="${action.onclick}">${action.label}</button>`
            ).join('') +
            '</div>';
    }
    
    notification.innerHTML = `
        <i class="fas ${icons[type] || icons.info}"></i>
        <span>${message}</span>
        ${actionsHTML}
        <button class="notification-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    document.body.appendChild(notification);
    
    if (duration > 0) {
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }
    
    return notification;
}

// ============================================
// MELHORIA 9: DEBOUNCE PARA BUSCAS
// ============================================
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Aplicar debounce nas buscas
if (typeof filterLeadsTable !== 'undefined') {
    const originalFilterLeads = filterLeadsTable;
    filterLeadsTable = debounce(originalFilterLeads, 300);
}

// ============================================
// INICIALIZAÇÃO
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    initializeAdvancedFilters();
    initializeMobileOptimizations();
    initializeAccessibility();
    initializeLazyLoading();
    
    // Adicionar ID ao main para skip link
    const main = document.querySelector('main');
    if (main) {
        main.id = 'main-content';
    }
});

