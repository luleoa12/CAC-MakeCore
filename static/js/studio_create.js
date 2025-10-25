document.addEventListener('DOMContentLoaded', function() {
  const form = document.querySelector('.studio-form');
  const submitBtn = form?.querySelector('button[type="submit"]');
  
  if (!form || !submitBtn) return;
  
  const originalBtnText = submitBtn.textContent;
  
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Creating...';
    submitBtn.style.opacity = '0.7';
    submitBtn.style.cursor = 'not-allowed';
    
    try {
      const formData = new FormData(form);
      
      const response = await fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      
      if (response.redirected) {
        window.location.href = response.url;
      } else {
        const result = await response.json();
        throw new Error(result.error || 'Failed to create studio');
      }
    } catch (error) {
      console.error('Error:', error);
      alert(error.message || 'An error occurred while creating the studio');
      
      submitBtn.disabled = false;
      submitBtn.textContent = originalBtnText;
      submitBtn.style.opacity = '';
      submitBtn.style.cursor = '';
    }
  });
});
