document.addEventListener('DOMContentLoaded', function() {
  const leftArrow = document.querySelector('.shared-arrow-left');
  const rightArrow = document.querySelector('.shared-arrow-right');
  const list = document.querySelector('.shared-projects-list');
  const scrollAmount = 300;

  function updateArrows() {
    leftArrow.classList.toggle('disabled', list.scrollLeft <= 0);
    rightArrow.classList.toggle('disabled', 
      list.scrollLeft + list.clientWidth >= list.scrollWidth);
  }

  leftArrow.addEventListener('click', () => {
    if (!leftArrow.classList.contains('disabled')) {
      list.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
    }
  });

  rightArrow.addEventListener('click', () => {
    if (!rightArrow.classList.contains('disabled')) {
      list.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  });

  list.addEventListener('scroll', updateArrows);
  updateArrows(); // Initial check
});

document.getElementById('showTierListBtn').onclick = function() {
  document.getElementById('tierListModal').style.display = 'flex';
};
document.getElementById('closeTierListModal').onclick = function() {
  document.getElementById('tierListModal').style.display = 'none';
};
window.addEventListener('click', function(event) {
  var modal = document.getElementById('tierListModal');
  if (event.target === modal) {
    modal.style.display = 'none';
  }
});

const programs = [
  {% for p in programs %}
    {
      id: "{{ p.id }}",
      name: "{{ p.name|e }}",
      image: "{{ p.image_url }}",
      tier: "{{ p.tier }}"
    },
  {% endfor %}
];
function createProgramCard(program) {
  const card = document.createElement('div');
  card.className = 'program-card';
  card.draggable = true;
  card.dataset.id = program.id;
  card.innerHTML = `
    <div class="program-card-img-container">
      <img src="${program.image}" alt="${program.name}" />
      <button class="info-button" tabindex="-1" onclick="event.stopPropagation(); event.preventDefault(); showProgramInfo('${program.name}', '${program.tier || ''}')">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-info">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 16v-4"/>
          <path d="M12 8h.01"/>
        </svg>
      </button>
      <div class="program-title">${program.name}</div>
    </div>
  `;
  card.addEventListener('dragstart', e => {
    e.dataTransfer.setData('text/plain', program.id);
    // Add ghost class to original card
    setTimeout(() => card.classList.add('drag-ghost'), 0);
    // Store original parent and index for reordering
    card.dataset.originalParent = card.parentElement.id;
    card.dataset.originalIndex = Array.from(card.parentElement.children).indexOf(card);
  });
  card.addEventListener('dragend', e => {
    card.classList.remove('drag-ghost');
    // Remove all placeholders
    document.querySelectorAll('.drop-placeholder').forEach(ph => ph.remove());
    document.querySelectorAll('.tier-dropzone').forEach(z => z.classList.remove('drag-over'));
  });
  return card;
}
function showProgramInfo(name, tier) {
  alert(`${name} (Tier: ${tier})`);
}
function setupTierList() {

  const dropzones = {};
  document.querySelectorAll('.tier-dropzone').forEach(zone => {
    dropzones[zone.id.replace('dropzone-', '')] = zone;
    zone.innerHTML = '';
  });
  programs.forEach(p => {
    const tier = p.tier || 'N/A';
    const zone = dropzones[tier] || dropzones['N/A'];
    zone.appendChild(createProgramCard(p));
  });

  document.querySelectorAll('.tier-dropzone').forEach(dropzone => {
    dropzone.addEventListener('dragover', e => {
      e.preventDefault();
      dropzone.classList.add('drag-over');
      const draggingId = document.querySelector('.program-card.drag-ghost')?.dataset.id;
      // Remove all .shift-right classes
      dropzone.querySelectorAll('.program-card.shift-right').forEach(card => card.classList.remove('shift-right'));
      // Find which card to shift
      let insertBefore = null;
      for (const child of dropzone.children) {
        if (!child.classList.contains('program-card')) continue;
        const rect = child.getBoundingClientRect();
        if (e.clientX < rect.left + rect.width / 2) {
          insertBefore = child;
          break;
        }
      }
      // Shift the card aside
      if (insertBefore) insertBefore.classList.add('shift-right');
      // Only one placeholder
      let placeholder = dropzone.querySelector('.drop-placeholder');
      if (!placeholder) {
        placeholder = document.createElement('div');
        placeholder.className = 'drop-placeholder';
      }
      if (insertBefore !== placeholder.nextSibling) {
        dropzone.insertBefore(placeholder, insertBefore);
      }
      // Remove any extra placeholders
      Array.from(dropzone.querySelectorAll('.drop-placeholder')).forEach(ph => { if (ph !== placeholder) ph.remove(); });
    });
    dropzone.addEventListener('dragleave', e => {
      dropzone.classList.remove('drag-over');
      dropzone.querySelectorAll('.drop-placeholder').forEach(ph => ph.remove());
      dropzone.querySelectorAll('.program-card.shift-right').forEach(card => card.classList.remove('shift-right'));
    });
    dropzone.addEventListener('drop', e => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      const id = e.dataTransfer.getData('text/plain');
      const card = document.querySelector(`.program-card[data-id='${id}']`);
      const ph = dropzone.querySelector('.drop-placeholder');
      if (card && ph) {
        dropzone.insertBefore(card, ph);
        ph.remove();
      } else if (card) {
        dropzone.appendChild(card);
      }
      saveTierList();
      // Remove all placeholders
      document.querySelectorAll('.drop-placeholder').forEach(ph => ph.remove());
      // Remove all .shift-right classes
      dropzone.querySelectorAll('.program-card.shift-right').forEach(card => card.classList.remove('shift-right'));

    });
  });
}

function saveTierList() {
  const tiers = {};
  document.querySelectorAll('.tier-dropzone').forEach(zone => {
    const tier = zone.id.replace('dropzone-', '');
    tiers[tier] = Array.from(zone.children).map(card => card.dataset.id);
  });
  fetch('/dashboard/save_tiers', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(tiers)
  })
}
document.addEventListener('DOMContentLoaded', setupTierList);

function openPreviewModal(id, name, image) {
  const modal = document.getElementById('previewModal');
  document.getElementById('modalImage').src = image;
  document.getElementById('modalTitle').textContent = name;
  document.getElementById('editProjectBtn').href = `/programs/${id}/edit`;
  modal.style.display = 'block';
}
function closePreviewModal() {
  document.getElementById('previewModal').style.display = 'none';
}
window.onclick = function(event) {
  const modal = document.getElementById('previewModal');
  if (event.target == modal) {
    modal.style.display = 'none';
  }
}
