(() => {
  const searchInput = document.querySelector('#college-search');
  const suggestions = document.querySelector('#college-suggestions');
  const searchForm = document.querySelector('#college-search-form');
  const resultsList = document.querySelector('#results-list');
  const filtersForm = document.querySelector('#filters-form');
  const filterPanel = document.querySelector('#filter-panel');
  const resultsTitle = document.querySelector('#results-title');
  const resultsSubtitle = document.querySelector('#results-subtitle');
  const selectedPill = document.querySelector('#selected-college-pill');
  const resultsCount = document.querySelector('#results-count');
  const mapElement = document.querySelector('#map');
  const useLocationButton = document.querySelector('#use-location');
  const locationStatus = document.querySelector('#location-status');
  if (!searchInput || !resultsList || !mapElement) return;

  let selectedCollege = null;
  let suggestionItems = [];
  let highlightedSuggestion = -1;
  let map;
  let collegeMarker;
  let radiusCircle;
  let currentLocationMarker;
  let currentLocationCircle;
  let currentLocation = null;
  const markers = new Map();

  const initMap = () => {
    if (map || !window.L) return;
    map = L.map(mapElement, { zoomControl: false }).setView([17.43, 78.44], 11);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);
  };

  const renderSuggestions = (colleges) => {
    suggestionItems = colleges;
    highlightedSuggestion = -1;
    suggestions.innerHTML = colleges.map((college, index) => `
      <button type="button" class="suggestion" role="option" data-suggestion-index="${index}">
        <span class="suggestion-icon">⌖</span><span><strong>${HF.escape(college.short_name)}${college.distance_km !== undefined ? ` <em>${Number(college.distance_km).toFixed(1)} km away</em>` : ''}</strong><small>${HF.escape(college.name)} · ${HF.escape(college.area)}</small></span>
      </button>`).join('');
    suggestions.querySelectorAll('[data-suggestion-index]').forEach((button) => {
      button.addEventListener('click', () => chooseCollege(suggestionItems[Number(button.dataset.suggestionIndex)]));
    });
  };

  const setLocationStatus = (message, kind = '') => {
    if (!locationStatus) return;
    locationStatus.textContent = message;
    locationStatus.className = `location-status ${kind}`.trim();
  };

  const showCurrentLocationOnMap = (latitude, longitude, accuracy = 0) => {
    initMap();
    if (!map) return;
    currentLocationMarker?.remove();
    currentLocationCircle?.remove();
    currentLocationMarker = L.marker([latitude, longitude], {
      icon: L.divIcon({ className: '', html: '<span class="current-location-marker">●</span>', iconSize: [22, 22], iconAnchor: [11, 11] }),
      zIndexOffset: 1000,
    }).addTo(map).bindPopup('<strong>Your current location</strong><br><small>Only used in this browser session</small>');
    if (accuracy > 0 && accuracy < 10000) {
      currentLocationCircle = L.circle([latitude, longitude], { radius: accuracy, color: '#16a89a', weight: 1, fillColor: '#16a89a', fillOpacity: .08 }).addTo(map);
    }
    if (!selectedCollege) map.setView([latitude, longitude], 13);
  };

  const fetchNearbyColleges = (latitude, longitude) => fetch(`/api/colleges/nearby?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}&radius=50&limit=10`).then(async (response) => {
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Could not find nearby colleges.');
    return payload;
  });

  const locateUser = () => {
    if (!window.isSecureContext && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      setLocationStatus('Location access needs HTTPS when you open the app from another device.', 'error');
      HF.toast('Open the app on HTTPS or use localhost for location access.', 'error');
      return;
    }
    if (!navigator.geolocation) {
      setLocationStatus('This browser does not support location access. Search for your college instead.', 'error');
      return;
    }
    useLocationButton.disabled = true;
    setLocationStatus('Requesting your location…');
    navigator.geolocation.getCurrentPosition(async (position) => {
      const { latitude, longitude, accuracy } = position.coords;
      currentLocation = { latitude, longitude, accuracy };
      showCurrentLocationOnMap(latitude, longitude, accuracy);
      try {
        const payload = await fetchNearbyColleges(latitude, longitude);
        if (!payload.colleges?.length) {
          renderSuggestions([]);
          setLocationStatus('No seeded colleges were found within 50 km. Search by college name instead.', 'error');
          return;
        }
        setLocationStatus(`Found ${payload.colleges.length} college${payload.colleges.length === 1 ? '' : 's'} near you. Choose one below.`, 'success');
        renderSuggestions(payload.colleges);
        suggestions.classList.add('location-suggestions');
        suggestions.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (error) {
        setLocationStatus(error.message, 'error');
      } finally {
        useLocationButton.disabled = false;
      }
    }, (error) => {
      const message = error.code === 1
        ? 'Location permission was denied. Allow it in your browser settings or search by college name.'
        : error.code === 3
          ? 'Location lookup timed out. Try again or search by college name.'
          : 'We could not read your location. Try again or search by college name.';
      setLocationStatus(message, 'error');
      useLocationButton.disabled = false;
    }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 300000 });
  };

  const fetchSuggestions = async (query = '') => {
    try {
      const response = await fetch(`/api/colleges?q=${encodeURIComponent(query)}`);
      const payload = await response.json();
      renderSuggestions(payload.colleges || []);
    } catch (_) {
      suggestions.innerHTML = '';
    }
  };

  const chooseCollege = (college) => {
    if (!college) return;
    selectedCollege = college;
    searchInput.value = college.name;
    suggestions.innerHTML = '';
    selectedPill.textContent = `${college.short_name} · ${college.area}`;
    selectedPill.classList.remove('hidden');
    filterPanel.classList.remove('hidden');
    document.querySelector('#explorer').scrollIntoView({ behavior: 'smooth', block: 'start' });
    loadResults();
  };

  searchInput.addEventListener('focus', () => fetchSuggestions(searchInput.value.trim()));
  useLocationButton?.addEventListener('click', locateUser);
  let inputTimer;
  searchInput.addEventListener('input', () => {
    selectedCollege = null;
    selectedPill.classList.add('hidden');
    window.clearTimeout(inputTimer);
    inputTimer = window.setTimeout(() => fetchSuggestions(searchInput.value.trim()), 170);
  });
  searchInput.addEventListener('keydown', (event) => {
    if (!suggestionItems.length) return;
    if (event.key === 'ArrowDown') { event.preventDefault(); highlightedSuggestion = Math.min(highlightedSuggestion + 1, suggestionItems.length - 1); }
    if (event.key === 'ArrowUp') { event.preventDefault(); highlightedSuggestion = Math.max(highlightedSuggestion - 1, 0); }
    if (event.key === 'Enter' && highlightedSuggestion >= 0) { event.preventDefault(); chooseCollege(suggestionItems[highlightedSuggestion]); }
    suggestions.querySelectorAll('.suggestion').forEach((item, index) => item.classList.toggle('active', index === highlightedSuggestion));
  });
  document.addEventListener('click', (event) => {
    if (!event.target.closest('.autocomplete-wrap')) suggestions.innerHTML = '';
  });

  searchForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!selectedCollege) {
      const query = searchInput.value.trim();
      if (query) {
        try {
          const response = await fetch(`/api/colleges?q=${encodeURIComponent(query)}`);
          const payload = await response.json();
          if (payload.colleges?.length) return chooseCollege(payload.colleges[0]);
        } catch (_) { /* the friendly message below is enough */ }
      }
      HF.toast('Select a college from the suggestions first.', 'error');
      searchInput.focus();
      return;
    }
    loadResults();
  });
  document.querySelectorAll('[data-college-query]').forEach((button) => {
    button.addEventListener('click', async () => {
      searchInput.value = button.dataset.collegeQuery;
      try {
        const response = await fetch(`/api/colleges?q=${encodeURIComponent(searchInput.value)}`);
        const payload = await response.json();
        chooseCollege(payload.colleges?.[0]);
      } catch (_) { HF.toast('College suggestions are unavailable right now.', 'error'); }
    });
  });

  const showSkeletons = () => { resultsList.innerHTML = '<div class="loading-card"></div><div class="loading-card"></div><div class="loading-card"></div>'; };
  const filterParams = () => {
    const data = new FormData(filtersForm);
    const params = new URLSearchParams({ college_id: selectedCollege.id });
    for (const [key, value] of data.entries()) if (value) params.set(key, value);
    return params;
  };

  const renderCard = (hostel) => {
    const cover = hostel.media?.[0];
    const image = cover ? `<img src="${HF.escape(cover.thumbnail_url)}" alt="${HF.escape(hostel.name)} sample media">` : '<span>⌂</span>';
    return `<article class="result-card" data-hostel-id="${hostel.id}" tabindex="0">
      <div class="result-image">${image}</div><div class="result-main"><div class="result-head"><h3>${HF.escape(hostel.name)}</h3><span class="type-badge type-${HF.escape(hostel.hostel_type)}">${HF.escape(hostel.hostel_type.replace('-', ' '))}</span></div>
      <p class="result-subtitle">${HF.escape(hostel.area)} · ${HF.escape(hostel.sharing_type)} sharing</p><div class="rating-line">${HF.stars(hostel.rating)} <small>${hostel.review_count ? `${hostel.rating.toFixed(1)} · ${hostel.review_count} review${hostel.review_count === 1 ? '' : 's'}` : 'No reviews yet'}</small></div>
      <div class="distance-line"><span>⌖</span> ${hostel.distance_km.toFixed(2)} km · about ${hostel.walking_minutes} min walk</div><div class="result-footer"><span class="price">₹${Number(hostel.price_min).toLocaleString('en-IN')} <small>/ month</small></span>${hostel.is_sample ? '<span class="sample-label">✦ Sample data</span>' : '<span class="sample-label">Community listing</span>'}</div></div></article>`;
  };

  const highlight = (hostelId, active = true) => {
    document.querySelectorAll('.result-card').forEach((card) => card.classList.toggle('highlighted', active && card.dataset.hostelId === String(hostelId)));
    markers.forEach((marker, id) => {
      const element = marker.getElement();
      if (element) element.classList.toggle('highlighted', active && id === Number(hostelId));
    });
  };

  const renderMap = (payload) => {
    initMap();
    if (!map) return;
    markers.forEach((marker) => marker.remove());
    markers.clear();
    collegeMarker?.remove();
    radiusCircle?.remove();
    const college = payload.college;
    collegeMarker = L.marker([college.latitude, college.longitude], { icon: L.divIcon({ className: '', html: '<span class="college-marker">⌖</span>', iconSize: [35, 35], iconAnchor: [17, 17] }) }).addTo(map).bindPopup(`<strong>${HF.escape(college.name)}</strong><br><small>Selected college</small>`);
    radiusCircle = L.circle([college.latitude, college.longitude], { radius: payload.radius_km * 1000, color: '#3567e8', weight: 1, fillColor: '#3567e8', fillOpacity: .06 }).addTo(map);
    const bounds = [[college.latitude, college.longitude]];
    if (currentLocation) bounds.push([currentLocation.latitude, currentLocation.longitude]);
    payload.hostels.forEach((hostel, index) => {
      bounds.push([hostel.latitude, hostel.longitude]);
      const marker = L.marker([hostel.latitude, hostel.longitude], { icon: L.divIcon({ className: '', html: `<span class="custom-marker" data-marker-id="${hostel.id}"><span>${index + 1}</span></span>`, iconSize: [30, 30], iconAnchor: [15, 28] }) }).addTo(map);
      marker.bindPopup(`<div class="popup-title">${HF.escape(hostel.name)}</div><div class="popup-meta">₹${Number(hostel.price_min).toLocaleString('en-IN')} / month · ${hostel.distance_km.toFixed(2)} km</div><div class="popup-meta">${HF.stars(hostel.rating)} ${hostel.review_count ? hostel.rating.toFixed(1) : 'New'}</div><a class="popup-link" href="/hostel/${hostel.id}">View details →</a>`);
      marker.on('mouseover', () => highlight(hostel.id));
      marker.on('mouseout', () => highlight(hostel.id, false));
      marker.on('click', () => { highlight(hostel.id); document.querySelector(`[data-hostel-id="${hostel.id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); });
      markers.set(hostel.id, marker);
    });
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [35, 35], maxZoom: 15 });
    else map.setView([college.latitude, college.longitude], 14);
    window.setTimeout(() => map.invalidateSize(), 100);
  };

  const renderResults = (payload) => {
    resultsTitle.textContent = `${payload.count} stay${payload.count === 1 ? '' : 's'} near ${payload.college.short_name}`;
    resultsSubtitle.textContent = `Within ${payload.radius_km} km · sorted by ${filtersForm.sort.value === 'price' ? 'lowest price' : filtersForm.sort.value === 'rating' ? 'top rating' : 'distance'}`;
    resultsCount.textContent = `${payload.count} result${payload.count === 1 ? '' : 's'}`;
    if (!payload.hostels.length) {
      resultsList.innerHTML = '<div class="empty-state compact"><span class="empty-icon">⌖</span><h3>No stays match those filters</h3><p>Try widening the radius or clearing one filter.</p><button class="button button-secondary button-small" id="empty-clear-filters" type="button">Clear filters</button></div>';
      document.querySelector('#empty-clear-filters')?.addEventListener('click', clearFilters);
    } else {
      resultsList.innerHTML = payload.hostels.map(renderCard).join('');
      resultsList.querySelectorAll('.result-card').forEach((card) => {
        const id = Number(card.dataset.hostelId);
        card.addEventListener('mouseenter', () => { highlight(id); markers.get(id)?.openPopup(); });
        card.addEventListener('mouseleave', () => highlight(id, false));
        card.addEventListener('click', (event) => { if (!event.target.closest('a')) window.location.href = `/hostel/${id}`; });
        card.addEventListener('keydown', (event) => { if (event.key === 'Enter') window.location.href = `/hostel/${id}`; });
      });
    }
    renderMap(payload);
  };

  const loadResults = async () => {
    if (!selectedCollege) return;
    showSkeletons();
    try {
      const response = await fetch(`/api/hostels?${filterParams().toString()}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Could not load stays.');
      renderResults(payload);
    } catch (error) {
      resultsList.innerHTML = `<div class="empty-state compact"><span class="empty-icon">!</span><h3>We couldn't load stays</h3><p>${HF.escape(error.message)}</p><button class="button button-secondary button-small" id="retry-results" type="button">Try again</button></div>`;
      document.querySelector('#retry-results')?.addEventListener('click', loadResults);
    }
  };

  const clearFilters = () => { filtersForm.reset(); filtersForm.radius.value = '5'; loadResults(); updateFilterCount(); };
  filtersForm?.addEventListener('submit', (event) => { event.preventDefault(); loadResults(); updateFilterCount(); });
  document.querySelector('#clear-filters')?.addEventListener('click', clearFilters);
  document.querySelector('#toggle-filters')?.addEventListener('click', () => filterPanel.classList.toggle('hidden'));
  const updateFilterCount = () => {
    const values = [...new FormData(filtersForm).entries()].filter(([key, value]) => value && !['radius', 'sort'].includes(key));
    const target = document.querySelector('.filter-count');
    if (target) target.textContent = values.length ? `(${values.length})` : '';
  };
  filtersForm?.addEventListener('change', updateFilterCount);
  initMap();
  updateFilterCount();
})();
