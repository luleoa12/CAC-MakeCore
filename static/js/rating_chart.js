
document.addEventListener('DOMContentLoaded', function() {
  let ratingData = [];
  let chart = null;
  
  function showError(message) {
    console.error('[ERROR]', message);
    const container = document.querySelector('.rating-chart-container');
    if (container) {
      container.innerHTML = `
        <div class="error-message">
          <i class="fas fa-exclamation-triangle"></i>
          <p>${message}</p>
        </div>
      `;
    }
  }

  // Function to update the rating display with the given data like date, rating, name, rank and that stuff
  function updateRatingDisplay(data) {
    const contestDateEl = document.getElementById('contestDate');
    const currentRatingEl = document.getElementById('currentRating');
    const contestNameEl = document.getElementById('contestName');
    const contestRankEl = document.getElementById('contestRank');
    const rankTitleEl = document.querySelector('.chart-header > div:last-child > div:first-child');
    
    if (!data) {
      data = ratingData[ratingData.length - 1];
      if (!data) return;
      
      const prevData = ratingData[ratingData.length - 2] || data;
      const change = data.rating - prevData.rating;
      
      if (currentRatingEl) currentRatingEl.textContent = data.rating.toLocaleString();
      
      if (contestDateEl) {
        contestDateEl.textContent = 'Global Rank';
        contestDateEl.style.fontWeight = '600';
      }
      if (contestNameEl) {
        contestNameEl.textContent = data.global_rank ? `#${data.global_rank.toLocaleString()}` : 'N/A';
      }
      
      // Right column to show contests attended
      if (rankTitleEl) rankTitleEl.textContent = 'Attended';
      if (contestRankEl) {
        contestRankEl.textContent = data.makejams_attended ? data.makejams_attended.toLocaleString() : '0';
      }
      
      // Rating change 
      const changeElement = document.getElementById('ratingChange');
      if (changeElement) {
        const changeIcon = document.getElementById('changeIcon');
        const changeValue = document.getElementById('changeValue');
        
        if (change > 0) {
          changeElement.style.color = '#2ecc71';
          changeElement.style.display = 'flex';
          if (changeIcon) changeIcon.textContent = '↑';
          if (changeValue) changeValue.textContent = Math.abs(change);
        } else if (change < 0) {
          changeElement.style.color = '#e74c3c';
          changeElement.style.display = 'flex';
          if (changeIcon) changeIcon.textContent = '↓';
          if (changeValue) changeValue.textContent = Math.abs(change);
        } else {
          changeElement.style.display = 'none';
        }
      }
      return;
    }
    
    // Hovering over a data point
    const dateParts = data.date.split('-');
    const date = new Date(dateParts[0], dateParts[1] - 1, dateParts[2] || 1);
    const formattedDate = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    
    // Update left column (rating)
    if (currentRatingEl) currentRatingEl.textContent = data.rating.toLocaleString();
    
    // Update middle column (date and contest name)
    if (contestDateEl) {
      contestDateEl.textContent = formattedDate;
      contestDateEl.style.fontWeight = '600';
    }

    if (contestNameEl) contestNameEl.textContent = data.contest ? data.contest.replace('Biweekly ', '') : 'N/A';
    
    // Update right column (rank)
    if (rankTitleEl) rankTitleEl.textContent = 'Rank';
    if (contestRankEl) contestRankEl.textContent = data.rank || 'N/A';
    
    const currentIndex = ratingData.findIndex(d => d.date === data.date);
    const changeElement = document.getElementById('ratingChange');
    
    if (changeElement) {
      changeElement.style.display = 'none';
      
      if (currentIndex > 0) {
        // Find the previous contest (skip any non-contest points)
        let prevIndex = currentIndex - 1;
        while (prevIndex >= 0 && ratingData[prevIndex].rank === 0) {
          prevIndex--;
        }
        
        // Only show change if we found a previous contest
        if (prevIndex >= 0) {
          const change = data.rating - ratingData[prevIndex].rating;
          const changeIcon = document.getElementById('changeIcon');
          const changeValue = document.getElementById('changeValue');
          
          if (changeIcon && changeValue) {
            changeElement.style.display = 'flex';
            changeElement.style.color = change >= 0 ? '#2ecc71' : '#e74c3c';
            changeIcon.textContent = change >= 0 ? '↑' : '↓';
            changeValue.textContent = Math.abs(change);
          }
        }
      }
    }
  }

  function initializeChart(data) {
    try {
      if (!Array.isArray(data)) {
        throw new Error('Invalid data format received from server');
      }
      
      ratingData = data;
      
      // 1200 is the first data point for all users
      if (ratingData.length === 0) {
        const today = new Date().toISOString().split('T')[0];
        ratingData = [{
          rating: 1200,
          date: today,
          contest: 'Initial Rating',
          rank: 1,
          global_rank: 0,
          makejams_attended: 0
        }];
      } else if (ratingData[0].rating !== 1200) {
        const firstDate = new Date(ratingData[0].date);
        const dayBefore = new Date(firstDate);
        dayBefore.setDate(firstDate.getDate() - 1);
        
        ratingData.unshift({
          rating: 1200,
          date: dayBefore.toISOString().split('T')[0],
          contest: 'Starting Rating',
          rank: 0,
          global_rank: 0,
          makejams_attended: 0
        });
      }



      const chartCanvas = document.getElementById('ratingChart');
      if (!chartCanvas) {
        throw new Error('Chart canvas element not found');
      }

      const ctx = chartCanvas.getContext('2d');
      if (!ctx) {
        throw new Error('Could not get 2D context for chart');
      }

      if (chart) {
        chart.destroy();
      }

      const ratings = ratingData.map(d => d.rating);
      const minRating = Math.min(1200, ...ratings);
      const maxRating = Math.max(1200, ...ratings);
      const padding = Math.max(50, (maxRating - minRating) * 0.2); 

      const style = getComputedStyle(document.documentElement);
      const color3Rgb = style.getPropertyValue('--color3-rgb').trim();
      chart = new Chart(ctx, {
        type: 'line',
        data: {
          // Show first and last date (year)
          labels: ratingData.map((d, i, arr) => {
            if (i === 0) {
              return new Date(d.date).getFullYear();
            } else if (i === arr.length - 1) {
              return new Date(d.date).getFullYear().toString();
            }
            return '';
          }),
          datasets: [{
            label: 'Rating',
            data: ratingData.map(d => d.rating),
            borderColor: `rgba(${color3Rgb}, 1)`,
            backgroundColor: `rgba(${color3Rgb}, 0.1)`,
            borderWidth: 3,
            pointBackgroundColor: ratingData.map((d, i) => {
              if (i === ratingData.length - 1) return `rgba(${color3Rgb}, 1)`;
              return `rgba(${color3Rgb}, 0.5)`;
            }),
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: `rgba(${color3Rgb}, 1)`,
            pointHoverRadius: 6,
            pointHoverBorderWidth: 2,
            pointRadius: ratingData.map((d, i) => i === ratingData.length - 1 ? 5 : 3),
            pointHitRadius: 10,
            tension: 0.3,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          onHover: (event, chartElement) => {
            const target = event.native ? event.native.target : event.target;
            if (chartElement.length > 0) {
              const dataIndex = chartElement[0].index;
              updateRatingDisplay(ratingData[dataIndex]);
              target.style.cursor = 'pointer';
            } else {
              updateRatingDisplay(ratingData[ratingData.length - 1]);
              target.style.cursor = 'default';
            }
          },
          plugins: {
            legend: {
              display: false
            },
            tooltip: {
              enabled: false
            }
          },
          scales: {
            x: {
              grid: {
                display: false,
                drawBorder: false
              },
              ticks: {
                color: '#666',
                font: {
                  size: 12
                },
                callback: function(val, index, ticks) {
                  if (index === 0 || index === ticks.length - 1) {
                    return this.getLabelForValue(val);
                  }
                  return '';
                }
              }
            },
            y: {
              grid: {
                color: 'rgba(0, 0, 0, 0.05)',
                drawBorder: false
              },
              ticks: {
                color: '#666',
                font: {
                  size: 12
                },
                callback: function(value) {
                  return value;
                }
              },
              min: Math.floor(minRating - padding),
              max: Math.ceil(maxRating + padding)
            }
          },
          interaction: {
            intersect: false,
            mode: 'index',
          },
          elements: {
            line: {
              borderJoinStyle: 'round'
            }
          }
        }
      });
      
      updateRatingDisplay(null);
      
      const chartElement = document.getElementById('ratingChart');
      if (chartElement) {
        chartElement.parentNode.addEventListener('mouseleave', function() {
          updateRatingDisplay(null);
        });
      }
      
    } catch (error) {
      console.error('Error initializing chart:', error);
      showError('Failed to initialize rating chart. ' + error.message);
    }
  }
  
  const chartContainer = document.getElementById('rating-chart-container');
  if (chartContainer) {
    chartContainer.addEventListener('mouseenter', () => {
      if (ratingData.length > 0) {
        updateRatingDisplay(ratingData[ratingData.length - 1]);
      }
    });
    
    chartContainer.addEventListener('mouseleave', () => {
      updateRatingDisplay(null);
    });
  }
  
  const pathSegments = window.location.pathname.split('/').filter(Boolean);
  const viewingOtherUser = pathSegments[0] === 'dashboard' && pathSegments.length > 1;
  const apiUrl = viewingOtherUser 
    ? `/api/user/${pathSegments[1]}/rating_history` 
    : '/api/user/rating_history';

  fetch(apiUrl)
    .then(response => {
      if (!response.ok) {
        return response.text().then(text => {
          throw new Error(`HTTP error! status: ${response.status}, body: ${text}`);
        });
      }
      return response.json();
    })
    .then(data => {
      if (Array.isArray(data)) {
        if (data.length > 0) {
          initializeChart(data);
        } else {
          showError('<span style="color: var(--color2); font-weight: 700; font-size: 1.2rem;">Participate in a MakeJam to see your rating!</span>');
        }
      } else {
        throw new Error('Invalid data format received from server');
      }
    })
    

});
