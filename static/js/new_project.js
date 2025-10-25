
document.addEventListener('DOMContentLoaded', function() {

  var permsSelect = document.getElementById('modPermsSelect');
  var permsModal = document.getElementById('modPermsModal');
  var closePermsBtn = document.getElementById('closeModPermsModal');
  var savePermsBtn = document.getElementById('saveModPermsBtn');
  var permsInput = document.getElementById('mod_perms');
  var permsUsernames = document.getElementById('modPermsUsernames');
  var chipsContainer = document.getElementById('modPermsChips');
  var chipsDropdown = document.getElementById('modPermsChipsDropdown');
  var modPermsCustomSelect = document.getElementById('modPermsCustomSelect');
  var modPermsCustomSelected = document.getElementById('modPermsCustomSelected');
  var modPermsCustomDropdown = document.getElementById('modPermsCustomDropdown');
  var modPermsAddPill = document.getElementById('modPermsAddPill');
  var suggestionsBox = document.getElementById('modPermsSuggestions');
  var errorBox = document.getElementById('modPermsError');

  let allUsernames = [];
  let selectedUsernames = [];

  function renderDropdown() {
    permsSelect.innerHTML = '';
    const opts = [
      { value: 'all', label: 'All' },
      { value: 'none', label: 'None' }
    ];
    opts.forEach(opt => {
      const o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.label;
      permsSelect.appendChild(o);
    });
    permsSelect.value = permsInput.value || 'all';
  }

  fetch('/api/usernames').then(r => r.json()).then(data => {
    allUsernames = data.usernames || [];
    renderDropdown();
    updateModPermsUI();
  });

  function renderChips() {
    chipsContainer.innerHTML = '';
    selectedUsernames.forEach(username => {
      const chip = document.createElement('span');
      chip.className = 'mod-chip';
      chip.innerHTML = `<span class="mod-chip-at">@</span>${username}<button type="button" class="mod-chip-x" title="Remove">&times;</button>`;
      chip.querySelector('.mod-chip-x').onclick = function() {
        selectedUsernames = selectedUsernames.filter(u => u !== username);
        renderChips();
        updateModPermsUI();
      };
      chipsContainer.appendChild(chip);
    });

    renderChipsDropdown();
  }

  function renderChipsDropdown() {
    chipsDropdown.innerHTML = '';
    if (selectedUsernames.length === 0) {

    } else {
      selectedUsernames.forEach(username => {
        const chip = document.createElement('span');
        chip.className = 'mod-chip';
        chip.innerHTML = `<span class="mod-chip-at">@</span>${username}<button type="button" class="mod-chip-x" title="Remove">&times;</button>`;
        chip.querySelector('.mod-chip-x').onclick = function(e) {
          e.stopPropagation();
          selectedUsernames = selectedUsernames.filter(u => u !== username);
          renderChips();
          updateModPermsUI();
        };
        chipsDropdown.appendChild(chip);
      });
    }

    const addPill = document.getElementById('modPermsAddPill');
    if (addPill && addPill.parentElement !== chipsDropdown.parentElement) {
      chipsDropdown.parentElement.appendChild(addPill);
    }
  }


  function showSuggestions(prefix) {
    if (!prefix || prefix.length < 1) {
      suggestionsBox.style.display = 'none';
      return;
    }
    let filtered = allUsernames.filter(u => u.toLowerCase().startsWith(prefix.toLowerCase()) && !selectedUsernames.includes(u));
    if (filtered.length === 0) {
      suggestionsBox.style.display = 'none';
      return;
    }
    suggestionsBox.innerHTML = '';
    filtered.forEach(u => {
      const opt = document.createElement('div');
      opt.className = 'mod-suggestion';
      opt.innerHTML = `<span class="mod-chip-at">@</span>${u}`;
      opt.onclick = function() {
        addChip(u);
        suggestionsBox.style.display = 'none';
        permsUsernames.value = '';
        permsUsernames.focus();
      };
      suggestionsBox.appendChild(opt);
    });
    const rect = permsUsernames.getBoundingClientRect();
    suggestionsBox.style.display = 'block';
    suggestionsBox.style.left = rect.left + 'px';
    suggestionsBox.style.top = (rect.bottom + window.scrollY) + 'px';
    suggestionsBox.style.width = rect.width + 'px';
  }

  function addChip(username) {
    if (!allUsernames.includes(username)) {
      errorBox.style.display = 'block';
      errorBox.textContent = `User @${username} does not exist.`;
      return;
    }
    if (selectedUsernames.includes(username)) return;
    selectedUsernames.push(username);
    renderChips();
    errorBox.style.display = 'none';
  }

  permsUsernames.addEventListener('input', function(e) {
    errorBox.style.display = 'none';
    let val = permsUsernames.value;
    let atMatches = val.match(/@([a-zA-Z0-9_]{1,30})/g);
    if (atMatches) {
      atMatches.forEach(tag => {
        let uname = tag.replace('@', '');
        if (uname && allUsernames.includes(uname) && !selectedUsernames.includes(uname)) {
          addChip(uname);
          permsUsernames.value = permsUsernames.value.replace(tag, '').trim();
        }
      });
    }

    let lastAt = val.lastIndexOf('@');
    if (lastAt !== -1) {
      let prefix = val.slice(lastAt + 1);
      showSuggestions(prefix);
    } else {
      suggestionsBox.style.display = 'none';
    }
  });

  permsUsernames.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      let val = permsUsernames.value.trim();
      if (val.startsWith('@')) val = val.slice(1);
      if (val && allUsernames.includes(val) && !selectedUsernames.includes(val)) {
        addChip(val);
        permsUsernames.value = '';
        suggestionsBox.style.display = 'none';
      } else if (val) {
        errorBox.style.display = 'block';
        errorBox.textContent = `User @${val} does not exist.`;
      }
    } else if (e.key === 'ArrowDown' && suggestionsBox.style.display === 'block') {
      let first = suggestionsBox.querySelector('.mod-suggestion');
      if (first) first.focus();
    }
  });

  document.addEventListener('click', function(e) {
    if (!suggestionsBox.contains(e.target) && e.target !== permsUsernames) {
      suggestionsBox.style.display = 'none';
    }
  });

  savePermsBtn.onclick = function() {
    if (selectedUsernames.length === 0) {
      errorBox.style.display = 'block';
      errorBox.textContent = 'Please add at least one moderator.';
      return;
    }
    permsInput.value = selectedUsernames.join(',');
    permsModal.style.display = 'none';
    permsSelect.value = 'more';
    renderChipsDropdown();
  };

  modPermsSelect.onchange = function() {
    if (this.value === 'all' || this.value === 'none') {
      permsInput.value = this.value;
      selectedUsernames = [];
      renderChips();
      updateModPermsUI();
      errorBox.style.display = 'none';
    }
  };

  modPermsAddPill.onclick = function() {
    permsModal.style.display = 'flex';
    setTimeout(() => permsUsernames.focus(), 100);
  };

  closePermsBtn.onclick = function() {
    permsModal.style.display = 'none';
    permsSelect.value = permsInput.value || 'all';
    errorBox.style.display = 'none';
  };

  permsModal.onclick = function(e) {
    if (e.target === permsModal) permsModal.style.display = 'none';
  };

  function updateModPermsUI() {
    modPermsAddPill.style.display = '';
    if (selectedUsernames.length === 0) {
      modPermsCustomSelect.style.display = '';
      modPermsCustomSelected.textContent = permsInput.value === 'none' ? 'None' : 'All';
      updateDropdownCheckmark();
    } else {
      modPermsCustomSelect.style.display = 'none';
    }
    renderChipsDropdown();
  }

  function updateDropdownCheckmark() {
    var opts = Array.from(modPermsCustomDropdown.getElementsByClassName('mod-perms-custom-option'));
    opts.forEach(opt => {
      var check = opt.querySelector('.mod-perms-check');
      if (opt.getAttribute('data-value') === permsInput.value) {
        check.style.display = 'inline';
      } else {
        check.style.display = 'none';
      }
    });
  }

  modPermsCustomSelect.onclick = function(e) {
    e.stopPropagation();
    if (modPermsCustomDropdown.style.display === 'block') {
      modPermsCustomDropdown.style.display = 'none';
    } else {
      modPermsCustomDropdown.style.display = 'block';
      updateDropdownCheckmark();
    }
  };
  Array.from(modPermsCustomDropdown.getElementsByClassName('mod-perms-custom-option')).forEach(opt => {
    opt.onclick = function(ev) {
      ev.stopPropagation();
      var val = this.getAttribute('data-value');
      permsInput.value = val;
      selectedUsernames = [];
      modPermsCustomSelected.textContent = val === 'none' ? 'None' : 'All';
      modPermsCustomDropdown.style.display = 'none';
      updateModPermsUI();
      errorBox.style.display = 'none';
      updateDropdownCheckmark();
    };
  });
  document.addEventListener('click', function(e) {
    if (!modPermsAddPill.contains(e.target) && !permsModal.contains(e.target)) {
      modPermsCustomDropdown.style.display = 'none';
    }
  });

  renderChips();
  updateModPermsUI();


  const dropzone = document.getElementById('image-dropzone');
  const imageInput = document.getElementById('image');
  const previewImg = document.getElementById('image-preview');
  const dropzoneText = document.getElementById('dropzone-text');

  function showPreview(file) {
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = function(ev) {
        previewImg.src = ev.target.result;
        previewImg.style.display = 'block';
        if (dropzoneText) dropzoneText.style.display = 'none';
      };
      reader.readAsDataURL(file);
    } else {
      previewImg.src = '';
      previewImg.style.display = 'none';
      if (dropzoneText) dropzoneText.style.display = 'block';
    }
  }

  imageInput.addEventListener('change', function(e) {
    const file = this.files && this.files[0];
    showPreview(file);
  });

  dropzone.addEventListener('dragover', function(e) {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', function(e) {
    dropzone.classList.remove('dragover');
  });
  dropzone.addEventListener('drop', function(e) {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files && files[0] && files[0].type.startsWith('image/')) {
      imageInput.files = files;
      showPreview(files[0]);
    }
  });

  dropzone.tabIndex = 0; 
  dropzone.addEventListener('keydown', function(e) {
    if ((e.key === 'Backspace' || e.key === 'Delete') && previewImg.style.display === 'block') {
      imageInput.value = '';
      previewImg.src = '';
      previewImg.style.display = 'none';
      if (dropzoneText) dropzoneText.style.display = 'block';
      e.preventDefault();
    }
  });
});
