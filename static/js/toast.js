
(function() {

  const typeIcons = {
    success: '<svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="8" fill="#e7faef"/><path d="M9 14.5L13 18L19 10" stroke="#2de47a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    info: '<svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="8" fill="#fff6e7"/><circle cx="14" cy="14" r="5" fill="#ffc44d"/><rect x="13" y="10" width="2" height="6" rx="1" fill="#ff9100"/></svg>',
    error: '<svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="8" fill="#ffe7e7"/><circle cx="14" cy="14" r="5" fill="#ff4d4f"/><rect x="13" y="10" width="2" height="6" rx="1" fill="#ff7a7a"/></svg>'
  };
  const typeClasses = {
    success: 'toast-success',
    info: 'toast-info',
    error: 'toast-error'
  };
  function createToast(title, desc = '', type = "info", duration = 3500) {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast ' + (typeClasses[type] || 'toast-info');
    // Icon
    const iconHtml = `<span class="toast-icon">${typeIcons[type] || typeIcons.info}</span>`;
    // Content
    const contentHtml = `<div class="toast-content"><div class="toast-title">${title}</div>${desc ? `<div class="toast-desc">${desc}</div>` : ''}</div>`;
    // Close
    const closeHtml = `<button class="toast-close" aria-label="Close">&times;</button>`;
    // Progress bar
    const progressHtml = `<div class="toast-progress"></div>`;
    toast.innerHTML = iconHtml + contentHtml + closeHtml + progressHtml;
    container.appendChild(toast);
    // Animate in
    setTimeout(() => toast.classList.add('toast-show'), 30);
    // Animate progress bar
    const progress = toast.querySelector('.toast-progress');
    progress.style.transition = `width ${duration}ms linear`;
    setTimeout(() => progress.style.width = '0%', 50);
    // Remove after duration
    const remove = () => {
      toast.classList.remove('toast-show');
      setTimeout(() => toast.remove(), 300);
    };
    toast.querySelector('.toast-close').onclick = remove;
    setTimeout(remove, duration);
  }

  window.showToast = createToast;
})();

