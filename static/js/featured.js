const slides = document.querySelectorAll('.carousel-item');
const dots = document.querySelectorAll('.dot');
let currentIndex = 0;

function showSlide(index) {
  slides.forEach((slide, i) => {
    slide.style.display = i === index ? "block" : "none";
    const iframe = slide.querySelector('iframe');
    const overlay = slide.querySelector('.play-overlay');
    const playButton = slide.querySelector('.play-button');
    const isMakeCode = slide.querySelector('.game-container-makecode') !== null;
    const isScratch = slide.querySelector('.game-container-scratch') !== null;

    if (!iframe || !overlay || !playButton) return;

    // Overlay behavior
    if (isMakeCode) {
      overlay.style.display = i === index ? "flex" : "none";
      if (i === index && iframe.dataset.loaded === "true") {
        iframe.style.display = "block";
        overlay.style.display = "none";
      } else {
        iframe.style.display = "none";
      }
    } else if (isScratch) {
      // For Scratch, lazy-load like MakeCode and support Play overlay
      overlay.style.display = i === index ? "flex" : "none";
      if (i === index && iframe.dataset.loaded === "true") {
        iframe.style.display = "block";
        overlay.style.display = "none";
      } else {
        iframe.style.display = "none";
      }
    }

    if (dots[i]) dots[i].classList.toggle("active", i === index);
  });

  currentIndex = index;
}

// Handle play button click
document.addEventListener('click', (e) => {
  if (e.target.closest('.play-button')) {
    const button = e.target.closest('.play-button');
    const slide = button.closest('.carousel-item');
    const iframe = slide.querySelector('iframe');
    const overlay = slide.querySelector('.play-overlay');
    const isMakeCode = slide.querySelector('.game-container-makecode') !== null;
    const isScratch = slide.querySelector('.game-container-scratch') !== null;

    if (isMakeCode || isScratch) {
      if (!iframe.src) {
        iframe.src = iframe.dataset.src;
        iframe.dataset.loaded = "true";
      }
      iframe.style.display = "block";
      overlay.style.display = "none";
    }
  }
});

// Rest of your existing functions...
function nextSlide() {
  showSlide((currentIndex + 1) % slides.length);
}

function prevSlide() {
  showSlide((currentIndex - 1 + slides.length) % slides.length);
}

function currentSlide(n) {
  showSlide(n - 1);
}

document.getElementById("prev-arrow").addEventListener("click", prevSlide);
document.getElementById("next-arrow").addEventListener("click", nextSlide);
window.currentSlide = currentSlide;

// Initialize
showSlide(0);