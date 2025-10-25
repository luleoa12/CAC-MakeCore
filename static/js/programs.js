document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM fully loaded');
  
  let isLoading = false;
  let currentPage = 1;
  let hasMore = true;
  let filterTimeout;
  let loadedProgramIds = new Set(); // Track loaded program IDs to prevent duplicates
  
  const STORAGE_KEYS = {
    SOURCE: 'programs_source_preference',
    SORT: 'programs_sort_preference',
    ORDER: 'programs_order_preference',
    FILTERS: 'programs_filter_preferences'
  };
  
  function saveToLocalStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.warn('Failed to save to localStorage:', error);
    }
  }
  
  function loadFromLocalStorage(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
      console.warn('Failed to load from localStorage:', error);
      return defaultValue;
    }
  }
  
  function saveSourcePreference(source) {
    saveToLocalStorage(STORAGE_KEYS.SOURCE, source);
  }
  
  function loadSourcePreference() {
    return loadFromLocalStorage(STORAGE_KEYS.SOURCE, 'all');
  }
  
  function saveSortPreference(sort, order) {
    saveToLocalStorage(STORAGE_KEYS.SORT, sort);
    saveToLocalStorage(STORAGE_KEYS.ORDER, order);
  }
  
  function loadSortPreference() {
    return {
      sort: loadFromLocalStorage(STORAGE_KEYS.SORT, 'upvotes'),
      order: loadFromLocalStorage(STORAGE_KEYS.ORDER, 'desc')
    };
  }
  
  function saveFilterPreferences() {
    const filterData = {
      logic: document.querySelector('.filter-logic-select')?.value || 'any',
      upvotes: {
        operator: document.querySelector('select[name="upvotes-operator"]')?.value || '',
        value: document.querySelector('input[name="upvotes-value"]')?.value || ''
      },
      downvotes: {
        operator: document.querySelector('select[name="downvotes-operator"]')?.value || '',
        value: document.querySelector('input[name="downvotes-value"]')?.value || ''
      },
      views: {
        operator: document.querySelector('select[name="views-operator"]')?.value || '',
        value: document.querySelector('input[name="views-value"]')?.value || ''
      },
      comments: {
        operator: document.querySelector('select[name="comments-operator"]')?.value || '',
        value: document.querySelector('input[name="comments-value"]')?.value || ''
      }
    };
    saveToLocalStorage(STORAGE_KEYS.FILTERS, filterData);
  }
  
  function loadFilterPreferences() {
    const saved = loadFromLocalStorage(STORAGE_KEYS.FILTERS, null);
    if (!saved) return;
    
    const logicSelect = document.querySelector('.filter-logic-select');
    if (logicSelect && saved.logic) {
      logicSelect.value = saved.logic;
    }
    
    ['upvotes', 'downvotes', 'views', 'comments'].forEach(field => {
      const operatorSelect = document.querySelector(`select[name="${field}-operator"]`);
      const valueInput = document.querySelector(`input[name="${field}-value"]`);
      
      if (saved[field]) {
        if (operatorSelect && saved[field].operator) {
          operatorSelect.value = saved[field].operator;
        }
        if (valueInput && saved[field].value) {
          valueInput.value = saved[field].value;
        }
      }
    });
  }
  
  function countActiveFilters() {
    let count = 0;
    
    ['upvotes', 'downvotes', 'views', 'comments'].forEach(field => {
      const operatorSelect = document.querySelector(`select[name="${field}-operator"]`);
      const valueInput = document.querySelector(`input[name="${field}-value"]`);
      
      if (operatorSelect && valueInput) {
        const operator = operatorSelect.value;
        const value = valueInput.value;
        
        if (operator && operator !== '' && value && value.trim() !== '') {
          count++;
        }
      }
    });
    
    return count;
  }
  
  function updateFilterButtonDisplay() {
    if (!filterToggle) return;
    
    const activeFilterCount = countActiveFilters();
    const filterIcon = filterToggle.querySelector('i:first-child');
    
    if (activeFilterCount > 0) {
      filterToggle.classList.add('has-filters');
      if (filterIcon) {
        filterIcon.className = 'bi bi-funnel-fill';
      }
      filterToggle.innerHTML = `<i class="bi bi-funnel-fill"></i> Filter (${activeFilterCount}) <i class="bi bi-chevron-down"></i>`;
    } else {
      filterToggle.classList.remove('has-filters');
      if (filterIcon) {
        filterIcon.className = 'bi bi-funnel';
      }
      filterToggle.innerHTML = `<i class="bi bi-funnel"></i> Filter <i class="bi bi-chevron-down"></i>`;
    }
  }
  
  const programsContainer = document.querySelector('.programs-scroll-container');
  const form = document.getElementById('programs-search-form');
  const searchInput = form ? form.querySelector('input[name="search"]') : null;
  const sortInput = document.getElementById('sort-input');
  const orderInput = document.getElementById('order-input');
  const sourceInput = document.getElementById('source-input');
  const filterToggle = document.getElementById('filter-toggle');
  const filterContent = document.getElementById('filter-content');
  const resetFiltersBtn = document.getElementById('reset-filters');
  const applyFiltersBtn = document.getElementById('apply-filters');
  const sortToggle = document.getElementById('sort-toggle');
  const sortContent = document.getElementById('sort-content');
  const sortOptions = document.querySelectorAll('.sort-option');
  const randomBtn = document.getElementById('random-program');
  const sourceToggle = document.getElementById('source-toggle');
  const sourceOptions = sourceToggle ? sourceToggle.querySelectorAll('.source-option') : [];
  const statsBadge = document.getElementById('stats-badge');
  
  function initFilterForm() {
    const params = new URLSearchParams(window.location.search);
    const filterLogic = params.get('filter_logic') || 'any';
    const logicSelect = document.querySelector('.filter-logic-select');
    if (logicSelect) logicSelect.value = filterLogic;
    
    let hasUrlFilters = false;
    ['upvotes', 'downvotes', 'views', 'comments'].forEach(field => {
      const op = params.get(`${field}_op`);
      const val = params.get(`${field}_val`);
      
      if (op && val) {
        hasUrlFilters = true;
        const opSelect = document.querySelector(`select[name="${field}-operator"]`);
        const valInput = document.querySelector(`input[name="${field}-value"]`);
        
        if (opSelect) opSelect.value = op;
        if (valInput) valInput.value = val;
      }
    });
    
    if (!hasUrlFilters) {
      loadFilterPreferences();
    }
    
    updateFilterButtonDisplay();
  }
  
  if (filterToggle && filterContent) {
    filterToggle.addEventListener('click', function(e) {
      e.stopPropagation();
      if (sortContent && sortContent.classList.contains('show')) {
        sortContent.classList.remove('show');
        sortToggle.classList.remove('active');
      }
      
      filterContent.classList.toggle('show');
      filterToggle.classList.toggle('active');
      
      if (filterContent.classList.contains('show')) {
        const closeOnOutsideClick = function(e) {
          if (!filterContent.contains(e.target) && e.target !== filterToggle) {
            filterContent.classList.remove('show');
            filterToggle.classList.remove('active');
            document.removeEventListener('click', closeOnOutsideClick);
          }
        };
        
        setTimeout(() => {
          document.addEventListener('click', closeOnOutsideClick);
        }, 0);
      }
    });
  }
  
  if (sortToggle && sortContent) {
    sortToggle.addEventListener('click', function(e) {
      e.stopPropagation();
      if (filterContent && filterContent.classList.contains('show')) {
        filterContent.classList.remove('show');
        filterToggle.classList.remove('active');
      }
      
      sortContent.classList.toggle('show');
      sortToggle.classList.toggle('active');
      
      if (sortContent.classList.contains('show')) {
        const closeOnOutsideClick = function(e) {
          if (!sortContent.contains(e.target) && e.target !== sortToggle) {
            sortContent.classList.remove('show');
            sortToggle.classList.remove('active');
            document.removeEventListener('click', closeOnOutsideClick);
          }
        };
        
        setTimeout(() => {
          document.addEventListener('click', closeOnOutsideClick);
        }, 0);
      }
    });
  }
  
  if (applyFiltersBtn) {
    applyFiltersBtn.addEventListener('click', function(e) {
      e.preventDefault();
      applyFilters();
    });
  }
  
  function applyFilters() {
    currentPage = 1;
    hasMore = true;
    loadedProgramIds.clear(); // Clear loaded programs
    programsContainer.innerHTML = '';
    
    // Check if all filter values are empty (just "-")
    const allFiltersEmpty = checkIfAllFiltersEmpty();
    
    if (allFiltersEmpty) {
      // Reset to default instead of applying filters
      resetFilters();
      return;
    }
    
    saveFilterPreferences();
    
    updateFilterButtonDisplay();
    
    updateURLWithFilters();
    
    loadPrograms();
  }
  
  function checkIfAllFiltersEmpty() {
    const fields = ['upvotes', 'downvotes', 'views', 'comments'];
    
    for (const field of fields) {
      const valueInput = document.querySelector(`input[name="${field}-value"]`);
      if (valueInput && valueInput.value && valueInput.value !== '-') {
        return false;
      }
    }
    
    return true; 
  }
  
  function updateURLWithFilters() {
    const params = new URLSearchParams();
    
    const filterLogicSelect = document.querySelector('.filter-logic-select');
    const filterLogic = filterLogicSelect ? filterLogicSelect.value : 'any';
    params.set('filter_logic', filterLogic);
    
    ['upvotes', 'downvotes', 'views', 'comments'].forEach(field => {
      const operatorSelect = document.querySelector(`select[name="${field}-operator"]`);
      const valueInput = document.querySelector(`input[name="${field}-value"]`);
      
      if (operatorSelect && valueInput) {
        const operator = operatorSelect.value;
        const value = valueInput.value;
        
        if (operator && operator !== '' && value) {
          params.set(`${field}_op`, operator);
          params.set(`${field}_val`, value);
        }
      }
    });
    
    const searchParams = new URLSearchParams(window.location.search);
    ['search', 'sort', 'order'].forEach(param => {
      const value = searchParams.get(param);
      if (value) params.set(param, value);
    });
    if (sourceInput && sourceInput.value && sourceInput.value !== 'all') {
      params.set('source', sourceInput.value);
    }
    
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, '', newUrl);
  }
  
  if (resetFiltersBtn) {
    resetFiltersBtn.addEventListener('click', function(e) {
      e.preventDefault();
      
      const filterLogicSelect = document.querySelector('.filter-logic-select');
      if (filterLogicSelect) filterLogicSelect.value = 'any';
      
      document.querySelectorAll('.filter-operator').forEach(select => {
        select.selectedIndex = 0; 
      });
      document.querySelectorAll('.filter-value').forEach(input => {
        input.value = '';
      });
      
      updateFilterButtonDisplay();
      
      currentPage = 1;
      hasMore = true;
      loadedProgramIds.clear(); // Clear loaded programs
      programsContainer.innerHTML = '';
      
      const params = new URLSearchParams(window.location.search);
      ['filter_logic', 'upvotes_op', 'upvotes_val', 'downvotes_op', 'downvotes_val', 'views_op', 'views_val', 'comments_op', 'comments_val'].forEach(param => {
        params.delete(param);
      });
      
      const newUrl = `${window.location.pathname}?${params.toString()}`;
      window.history.pushState({}, '', newUrl);
      
      try {
        localStorage.removeItem(STORAGE_KEYS.FILTERS);
      } catch (error) {
        console.warn('Failed to clear filter preferences from localStorage:', error);
      }
      
      loadPrograms();
    });
  }
  
  document.querySelectorAll('.filter-operator, .filter-value').forEach(element => {
    element.addEventListener('change', updateFilterButtonDisplay);
    element.addEventListener('input', updateFilterButtonDisplay);
  });
  
  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      const searchTerm = searchInput ? searchInput.value.trim() : '';
      
      const params = new URLSearchParams(window.location.search);
      
      if (searchTerm) {
        params.set('search', searchTerm);
      } else {
        params.delete('search');
      }
      
      params.set('page', '1');
      
      const newUrl = `${window.location.pathname}?${params.toString()}`;
      window.history.pushState({}, '', newUrl);
      
      currentPage = 1;
      hasMore = true;
      loadedProgramIds.clear(); // Clear loaded programs
      if (programsContainer) programsContainer.innerHTML = '';
      loadPrograms();
    });
  }

  function updateSourceUI() {
    let current = (sourceInput ? sourceInput.value : 'all') || 'all';
    
    if (current === 'all' && window.location.pathname) {
      if (window.location.pathname.includes('/scratch')) {
        current = 'scratch';
      } else if (window.location.pathname.includes('/makecode')) {
        current = 'makecode';
      }
      if (sourceInput) sourceInput.value = current;
    }
    
    if (sourceOptions && sourceOptions.length > 0) {
      sourceOptions.forEach(btn => {
        if (btn.getAttribute('data-source') === current) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });
    }
    if (statsBadge) {
      statsBadge.style.display = current === 'all' ? '' : 'none';
    }
  }

  function handleSourceChange(source) {
    if (sourceInput) {
      sourceInput.value = source;
      
      // Save source preference to localStorage
      saveSourcePreference(source);
      
      const params = new URLSearchParams(window.location.search);
      if (source && source !== 'all') {
        params.set('source', source);
      } else {
        params.delete('source');
      }
      params.set('page', '1');
      
      const newUrl = `${window.location.pathname}?${params.toString()}`;
      window.history.pushState({}, '', newUrl);
      
      currentPage = 1;
      hasMore = true;
      loadedProgramIds.clear(); // Clear loaded programs
      if (programsContainer) programsContainer.innerHTML = '';
      updateSourceUI();
      loadPrograms();
    }
  }

  if (sourceToggle && sourceOptions && sourceOptions.length > 0) {
    sourceOptions.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const source = btn.getAttribute('data-source');
        handleSourceChange(source);
      });
    });
    
    let urlSource = 'all';
    
    if (window.location.pathname.includes('/scratch')) {
      urlSource = 'scratch';
    } else if (window.location.pathname.includes('/makecode')) {
      urlSource = 'makecode';
    } else {
      const urlParams = new URLSearchParams(window.location.search);
      urlSource = urlParams.get('source') || loadSourcePreference();
    }
    
    if (sourceInput) {
      sourceInput.value = urlSource;
      updateSourceUI();
      
      window.addEventListener('popstate', () => {
        const params = new URLSearchParams(window.location.search);
        const newSource = params.get('source') || 'all';
        if (sourceInput.value !== newSource) {
          sourceInput.value = newSource;
          updateSourceUI();
          currentPage = 1;
          hasMore = true;
          loadedProgramIds.clear(); // Clear loaded programs
          if (programsContainer) programsContainer.innerHTML = '';
          loadPrograms();
        }
      });
    }
  }
  
  if (searchInput) {
    let searchTimeout;
    searchInput.addEventListener('input', function() {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        form.dispatchEvent(new Event('submit'));
      }, 500);
    });
  }
  
  function cycleSort(sortBy) {
    const currentSort = sortInput ? sortInput.value : '';
    const currentOrder = orderInput ? orderInput.value : '';
    
    let newSort = '';
    let newOrder = '';
    
    if (currentSort === sortBy) {
      if (currentOrder === 'desc') {
        newSort = sortBy;
        newOrder = 'asc';
      } else if (currentOrder === 'asc') {
        newSort = '';
        newOrder = '';
      } else {
        newSort = sortBy;
        newOrder = 'desc';
      }
    } else {
      newSort = sortBy;
      newOrder = 'desc';
    }
    
    if (sortInput) sortInput.value = newSort;
    if (orderInput) orderInput.value = newOrder;
    
    saveSortPreference(newSort, newOrder);
    
    const params = new URLSearchParams(window.location.search);
    if (newSort) {
      params.set('sort', newSort);
      params.set('order', newOrder);
    } else {
      params.delete('sort');
      params.delete('order');
    }
    
    params.set('page', '1');
    
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, '', newUrl);
    
    currentPage = 1;
    hasMore = true;
    loadedProgramIds.clear(); // Clear loaded programs
    programsContainer.innerHTML = '';
    loadPrograms();
    
    updateSortDisplay();
  }
  
  sortOptions.forEach(option => {
    option.addEventListener('click', function() {
      const sortBy = this.getAttribute('data-sort');
      if (sortBy) {
        cycleSort(sortBy);
      }
    });
  });
  
  function updateSortDisplay() {
    const currentSort = sortInput ? sortInput.value : '';
    const currentOrder = orderInput ? orderInput.value : '';
    
    if (sortToggle) {
      const sortIcon = sortToggle.querySelector('i:first-child');
      const sortText = sortToggle.querySelector('.sort-text');
      
      if (currentSort) {
        sortToggle.classList.add('active');
        
        if (sortText) {
          const sortLabels = {
            'upvotes': 'Upvotes',
            'downvotes': 'Downvotes', 
            'comments': 'Comments',
            'views': 'Views',
            'date': 'Date'
          };
          sortText.textContent = sortLabels[currentSort] || 'Sort';
        }
        
        if (sortIcon) {
          sortIcon.className = 'bi';
          
          if (currentOrder === 'asc') {
            sortIcon.classList.add('bi-arrow-up');
          } else if (currentOrder === 'desc') {
            sortIcon.classList.add('bi-arrow-down');
          } else {
            sortIcon.classList.add('bi-arrow-down-up');
          }
        }
      } else {
        sortToggle.classList.remove('active');
        if (sortText) {
          sortText.textContent = 'Sort';
        }
        if (sortIcon) {
          sortIcon.className = 'bi bi-arrow-down-up';
        }
      }
    }
    
    sortOptions.forEach(option => {
      const sortBy = option.getAttribute('data-sort');
      const icon = option.querySelector('i');
      
      option.classList.remove('active', 'asc', 'desc');
      
      if (sortBy === currentSort) {
        option.classList.add('active');
        
        if (currentOrder === 'asc') {
          option.classList.add('asc');
        } else if (currentOrder === 'desc') {
          option.classList.add('desc');
        }
        
        if (icon) {
          if (currentOrder === 'asc') {
            icon.className = 'bi bi-arrow-up';
          } else if (currentOrder === 'desc') {
            icon.className = 'bi bi-arrow-down';
          } else {
            icon.className = 'bi';
          }
        }
      } else {
        if (icon) {
          icon.className = 'bi';
        }
      }
    });
  }
  
  function initializeSortDisplay() {
    const params = new URLSearchParams(window.location.search);
    let sort = params.get('sort');
    let order = params.get('order');
    
    if (!sort) {
      const savedSort = loadSortPreference();
      sort = savedSort.sort;
      order = savedSort.order;
      
      params.set('sort', sort);
      params.set('order', order);
      const newUrl = `${window.location.pathname}?${params.toString()}`;
      window.history.replaceState({}, '', newUrl);
    }
    
    if (sortInput) sortInput.value = sort;
    if (orderInput) orderInput.value = order;
    
    updateSortDisplay();
  }
  
  initializeSortDisplay();
  
  window.addEventListener('popstate', initializeSortDisplay);
  
  async function loadPrograms() {
    if (isLoading || !hasMore) return;
    
    isLoading = true;
    showLoading(true);
    
    try {
      const params = new URLSearchParams({
        page: currentPage,
        ajax: '1' 
      });
      
      const searchTerm = searchInput ? searchInput.value.trim() : '';
      if (searchTerm) {
        params.set('search', searchTerm);
      }
      
      const currentSource = sourceInput ? sourceInput.value : 'all';
      if (currentSource && currentSource !== 'all') {
        params.set('source', currentSource);
      }
      
      const sortValue = sortInput ? sortInput.value : 'date';
      const orderValue = orderInput ? orderInput.value : 'desc';
      params.set('sort', sortValue);
      params.set('order', orderValue);
      
      const filterLogicSelect = document.querySelector('.filter-logic-select');
      const filterLogic = filterLogicSelect ? filterLogicSelect.value : 'any';
      params.set('filter_logic', filterLogic);
      
      const filterFields = ['upvotes', 'downvotes', 'views', 'comments'];
      filterFields.forEach(field => {
        const operatorSelect = document.querySelector(`select[name="${field}-operator"]`);
        const valueInput = document.querySelector(`input[name="${field}-value"]`);
        
        if (operatorSelect && valueInput) {
          const op = operatorSelect.value;
          const val = valueInput.value;
          if (op && op !== '' && val) {
            params.set(`${field}_op`, op);
            params.set(`${field}_val`, val);
          }
        }
      });
      
      const url = `/programs?${params.toString()}`;
      console.log('Fetching URL:', url);
      
      const response = await fetch(url, {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        },
        cache: 'no-store'
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Server response error:', errorText);
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      let data;
      try {
        data = await response.json();
        console.log('Received data:', data);
      } catch (jsonError) {
        console.error('Error parsing JSON:', jsonError);
        throw new Error('Invalid JSON response from server');
      }
      
      hasMore = data.has_next;
      
      if (data.programs && data.programs.length > 0) {
        renderPrograms(data.programs);
        currentPage++; 
      } else if (currentPage === 1) {
        showNoResults();
      } else {
        hasMore = false; 
      }
      
    } catch (error) {
      console.error('Error in loadPrograms:', error);
      showError(error.message || 'Failed to load programs. Please try again.');
    } finally {
      isLoading = false;
      showLoading(false);
    }
  }
  
  function renderPrograms(programs) {
    const container = programsContainer;
    
    programs.forEach(program => {
      if (loadedProgramIds.has(program.id)) {
        return;
      }
      
      loadedProgramIds.add(program.id);
      
      const programHtml = `
        <div class="program-card-wrapper">
          <a href="/program/${program.id}" style="text-decoration:none;">
            <div class="program-card-imgbox-outer">
              <div class="program-card-imgbox-inner">
                <img src="${program.image_url}" alt="${program.name}" class="program-card-img" loading="lazy" onerror="this.onerror=null; this.src='/static/themes/' + (document.documentElement.getAttribute('data-theme') || 'orange') + '/img/studio_default.svg';">
              </div>
              <div class="program-card-imgbox-border"></div>
            </div>
          </a>
          <a href="/program/${program.id}" style="text-decoration:none;">
            <div class="program-card-titlebox">
              <div class="program-card-title">${program.name}</div>
            </div>
          </a>
        </div>
      `;
      container.insertAdjacentHTML('beforeend', programHtml);
    });
  }
  
  function showLoading(show) {
    let loader = document.querySelector('.loading-spinner');
    if (show) {
      if (!loader) {
        loader = document.createElement('div');
        loader.className = 'loading-spinner';
        loader.innerHTML = '<div class="spinner-border text-primary"></div>';
        programsContainer.insertAdjacentElement('afterend', loader);
      }
      loader.style.display = 'flex';
    } else if (loader) {
      loader.style.display = 'none';
    }
  }
  
  function showNoResults() {
    const noResultsHTML = `
      <div class="no-results" style="
        background: rgba(var(--color1-rgb), 0.1);
        border: 1px solid var(--color1);
        border-radius: 12px;
        padding: 2.5rem 2rem;
        margin: 2rem auto;
        max-width: 600px;
        display: flex;
        align-items: center;
        gap: 1.5rem;
        text-align: left;
        font-family: 'Fira Code', monospace;
      ">
        <div style="
          background: var(--color1);
          color: white;
          width: 64px;
          height: 64px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          font-size: 1.4rem;
        ">
          <i class="bi bi-search" style="font-size: 1.8rem; margin-top: 15px; line-height: 1;"></i>
        </div>
        <div>
          <h3 style="
            margin: 0 0 0.5rem 0;
            color: var(--color7);
            font-size: 1.4rem;
            font-weight: 500;
            font-family: 'Fira Code', monospace;
          ">No programs found</h3>
          <p style="
            margin: 0;
            color: var(--color20);
            font-size: 1rem;
            line-height: 1.5;
            font-family: 'Fira Code', monospace;
          ">We couldn't find any programs matching your search. Try adjusting your filters or search terms.</p>
        </div>
      </div>
    `;
    
    programsContainer.innerHTML = noResultsHTML;
  }
  
  function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger';
    errorDiv.textContent = message;
    programsContainer.insertAdjacentElement('afterbegin', errorDiv);
    setTimeout(() => errorDiv.remove(), 5000);
  }
  
  function handleScroll() {
    if (isLoading || !hasMore) return;
    
    const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
    const scrollPosition = scrollTop + clientHeight;
    const threshold = scrollHeight - 500;
    
    if (scrollPosition >= threshold) {
      loadPrograms();
    }
  }
  
  if (randomBtn) {
    randomBtn.addEventListener('click', () => {
      window.location.href = '/program/random';
    });
  }

  initFilterForm();
  
  loadPrograms();
  
  window.addEventListener('scroll', handleScroll);
});
