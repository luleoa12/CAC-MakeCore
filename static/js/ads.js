document.addEventListener('DOMContentLoaded', function() {
    updateAdPosition();
    });
    function updateAdPosition() {
        const leftAd = document.getElementById('left-ad');
        const rightAd = document.getElementById('right-ad');
        if(!leftAd || !rightAd) return;
        const scrollPosition = window.scrollY;
        const viewportHeight = window.innerHeight;
        const navbarOffset = 35;
        
        if (scrollPosition <= navbarOffset) {
            const adHeight = leftAd.offsetHeight;
            const viewportHeight = window.innerHeight;
            const centerTop = (viewportHeight - adHeight) / 2 + navbarOffset;

            leftAd.style.top = centerTop + 'px';
            leftAd.style.transform = 'none'; 
            rightAd.style.top = centerTop + 'px';
            rightAd.style.transform = 'none'; 
        } else {
            leftAd.style.top = '50%';
            leftAd.style.transform = 'translateY(-50%)';
            rightAd.style.top = '50%';
            rightAd.style.transform = 'translateY(-50%)';
        }
    }
window.addEventListener('load', updateAdPosition);
window.addEventListener('scroll', updateAdPosition);
window.addEventListener('resize', updateAdPosition);


function updateBackgroundForAds(showAds) {
    const style = document.getElementById('bg-no-arrows-style');
    if (!style) return;

    if (showAds) {
        style.disabled = false;  // show the background when ads are on
    } else {
        style.disabled = true;   // hide the background when ads are off
    }
  }

  function updateAdsDisplay(show) {
      const leftAd = document.getElementById('left-ad');
      const rightAd = document.getElementById('right-ad');
  
      if (!leftAd || !rightAd) return;
  
      leftAd.style.display = show ? 'block' : 'none';
      rightAd.style.display = show ? 'block' : 'none';
  }
  
  document.addEventListener('DOMContentLoaded', () => {
      const showAdsServer = {{ 'true' if show_ads else 'false' }};
      updateBackgroundForAds(showAdsServer);
      updateAdsDisplay(showAdsServer);
  });