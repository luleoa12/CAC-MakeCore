

document.addEventListener('DOMContentLoaded', function() {
  const openModalBtn = document.getElementById('browse-projects-btn');
  const modal = document.getElementById('project-modal');
  const closeBtn = modal ? modal.querySelector('.close-button') : null;
  const doneBtn = document.getElementById('project-modal-done');
  const projectCards = document.querySelectorAll('.project-card-modal');

  if (openModalBtn && modal) {
    openModalBtn.addEventListener('click', function(e) {
      e.preventDefault();
      modal.style.display = 'flex';
    });
  }
  if (closeBtn) {
    closeBtn.addEventListener('click', function() {
      modal.style.display = 'none';
    });
  }
  if (doneBtn) {
    doneBtn.addEventListener('click', function() {
      modal.style.display = 'none';
    });
  }

  if (modal) {
    window.addEventListener('click', function(event) {
      if (event.target === modal) {
        modal.style.display = 'none';
      }
    });
  }

  projectCards.forEach(function(card) {
    card.addEventListener('click', function() {
      const isSelected = card.classList.toggle('selected');
      card.setAttribute('aria-checked', isSelected ? 'true' : 'false');
      const plus = card.querySelector('.plus-icon');
      const check = card.querySelector('.checkmark-svg');
      if (isSelected) {
        if (plus) plus.style.display = 'none';
        if (check) check.style.display = 'block';
      } else {
        if (plus) plus.style.display = 'block';
        if (check) check.style.display = 'none';
      }
    });

    const plus = card.querySelector('.plus-icon');
    const check = card.querySelector('.checkmark-svg');
    if (plus) plus.style.display = 'block';
    if (check) check.style.display = 'none';
  });
});
