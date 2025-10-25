// Followers Modal logic for dashboard.html
function openFollowersModal(followers) {
  const modalBg = document.createElement('div');
  modalBg.className = 'followers-modal-bg';
  modalBg.style.display = 'flex';
  modalBg.innerHTML = `
    <div class="followers-modal">
      <div class="followers-modal-header">
        <span class="followers-modal-title">Followers <span class="followers-modal-count">${followers.length}</span></span>
        <input type="text" class="followers-search" placeholder="Search Followers" oninput="filterFollowers()">
        <span class="followers-modal-close" style="font-size:2rem; color:#fff; cursor:pointer; margin-left:18px;">&times;</span>
      </div>
      <div class="followers-list">
        ${followers.map(u => `
          <div class="followers-card">
            <img class="followers-avatar" src="${u.profile_pic_url || '/static/themes/makecore/img/default_avatar.png'}" alt="${u.username}">
            <div class="followers-info">
              <div class="followers-name">${u.username}</div>
              <div class="followers-location">${u.location || ''}</div>
            </div>
            ${u.is_followed ? `<button class="followers-follow-btn followed">Followed</button>` : `<button class="followers-follow-btn">Follow</button>`}
          </div>
        `).join('')}
      </div>
    </div>
  `;
  document.body.appendChild(modalBg);
  // Close modal logic
  modalBg.querySelector('.followers-modal-close').onclick = () => document.body.removeChild(modalBg);
  modalBg.onclick = (e) => { if (e.target === modalBg) document.body.removeChild(modalBg); };
}

function filterFollowers() {
  const input = document.querySelector('.followers-search');
  const filter = input.value.toLowerCase();
  document.querySelectorAll('.followers-card').forEach(card => {
    const name = card.querySelector('.followers-name').textContent.toLowerCase();
    card.style.display = name.includes(filter) ? '' : 'none';
  });
}
