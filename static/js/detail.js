(() => {
  const dataElement = document.querySelector('#hostel-data');
  const page = document.querySelector('#detail-page');
  if (!dataElement || !page) return;
  let hostel = JSON.parse(dataElement.textContent);
  let editingReviewId = null;
  const currentUser = HF.user();

  const renderGallery = () => {
    const gallery = document.querySelector('#gallery');
    const empty = document.querySelector('#gallery-empty');
    const media = hostel.media || [];
    if (!media.length) { gallery.innerHTML = ''; empty.classList.remove('hidden'); return; }
    empty.classList.add('hidden');
    gallery.innerHTML = media.slice(0, 3).map((item) => {
      const source = item.media_type === 'video'
        ? `<video src="${HF.escape(item.url)}" muted preload="metadata"></video>`
        : `<img src="${HF.escape(item.thumbnail_url || item.url)}" alt="${HF.escape(item.original_name)}">`;
      return `<button class="gallery-item ${item.is_sample ? 'sample-media' : ''}" type="button" data-media-url="${HF.escape(item.url)}" data-media-type="${HF.escape(item.media_type)}">${source}</button>`;
    }).join('');
    gallery.querySelectorAll('[data-media-url]').forEach((button) => button.addEventListener('click', () => openLightbox(button.dataset.mediaUrl, button.dataset.mediaType)));
  };

  const openLightbox = (url, type) => {
    const lightbox = document.createElement('div');
    lightbox.className = 'lightbox';
    lightbox.innerHTML = `<button class="lightbox-close" type="button" aria-label="Close">×</button>${type === 'video' ? `<video src="${HF.escape(url)}" controls autoplay></video>` : `<img src="${HF.escape(url)}" alt="Hostel media">`}`;
    document.body.appendChild(lightbox);
    const close = () => lightbox.remove();
    lightbox.querySelector('.lightbox-close').addEventListener('click', close);
    lightbox.addEventListener('click', (event) => { if (event.target === lightbox) close(); });
    document.addEventListener('keydown', function escape(event) { if (event.key === 'Escape') { close(); document.removeEventListener('keydown', escape); } });
  };

  const categoryLabel = { cleanliness: 'Clean', food: 'Food', safety: 'Safety', value_for_money: 'Value', wifi: 'WiFi' };
  const renderReviews = () => {
    const list = document.querySelector('#reviews-list');
    const reviews = hostel.reviews || [];
    if (!reviews.length) { list.innerHTML = '<div class="empty-state compact"><span class="empty-icon">✦</span><h3>No reviews yet</h3><p>Be the first student to share what you learned.</p></div>'; return; }
    list.innerHTML = reviews.map((review) => `<article class="review-item" data-review-id="${review.id}">
      <div class="review-header"><div class="reviewer"><span class="reviewer-avatar">${HF.escape(review.reviewer.slice(0, 1).toUpperCase())}</span><div><strong>${HF.escape(review.reviewer)}</strong><small>${HF.escape(review.date)}</small></div></div><div>${HF.stars(review.overall_rating)} ${review.is_sample ? '<span class="sample-badge">Sample data</span>' : ''}</div></div>
      <p class="review-body">${HF.escape(review.body)}</p><div class="review-categories">${Object.keys(categoryLabel).map((key) => `<span>${categoryLabel[key]} ${review[key]}/5</span>`).join('')}</div>
      ${review.media?.length ? `<div class="review-media">${review.media.map((item) => item.media_type === 'image' ? `<img src="${HF.escape(item.thumbnail_url || item.url)}" alt="Review media">` : '<span class="sample-badge">Video</span>').join('')}</div>` : ''}
      <div class="review-actions"><button type="button" data-helpful>♧ Helpful <span>${review.helpful_count}</span></button>${review.can_edit ? '<button type="button" data-edit-review>Edit</button><button type="button" data-delete-review>Delete</button>' : ''}</div>
    </article>`).join('');
  };

  const renderSummary = () => {
    const rating = document.querySelector('.big-rating strong');
    const stars = document.querySelector('.big-rating .stars');
    const count = document.querySelector('.review-count-label');
    if (rating) rating.textContent = hostel.rating ? Number(hostel.rating).toFixed(1) : '—';
    if (stars) stars.outerHTML = HF.stars(hostel.rating);
    if (count) count.textContent = `${hostel.review_count} review${hostel.review_count === 1 ? '' : 's'}`;
  };

  const resetReviewForm = () => {
    const form = document.querySelector('#review-form');
    if (!form) return;
    form.reset(); editingReviewId = null;
    document.querySelector('#review-form-title').textContent = 'Write a review';
    document.querySelector('#cancel-review-edit').classList.add('hidden');
    document.querySelector('#review-form-message').textContent = '';
    form.querySelector('button[type="submit"]').innerHTML = 'Publish review <span>→</span>';
  };

  const startEdit = (review) => {
    const form = document.querySelector('#review-form');
    if (!form) return;
    editingReviewId = review.id;
    ['overall_rating', 'cleanliness', 'food', 'safety', 'value_for_money', 'wifi'].forEach((field) => { form.elements[field].value = review[field]; });
    form.elements.body.value = review.body;
    document.querySelector('#review-form-title').textContent = 'Edit your review';
    document.querySelector('#cancel-review-edit').classList.remove('hidden');
    form.querySelector('button[type="submit"]').innerHTML = 'Save changes <span>→</span>';
    document.querySelector('#review-form-wrap').scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  document.querySelector('#reviews-list')?.addEventListener('click', async (event) => {
    const item = event.target.closest('.review-item');
    if (!item) return;
    const review = hostel.reviews.find((entry) => entry.id === Number(item.dataset.reviewId));
    if (!review) return;
    if (event.target.closest('[data-edit-review]')) return startEdit(review);
    if (event.target.closest('[data-delete-review]')) {
      if (!window.confirm('Delete your review? This cannot be undone.')) return;
      try { await HF.request(`/api/reviews/${review.id}`, { method: 'DELETE' }); window.location.reload(); } catch (error) { HF.toast(error.message, 'error'); }
    }
    if (event.target.closest('[data-helpful]')) {
      try {
        const payload = await HF.request(`/api/reviews/${review.id}/helpful`, { method: 'POST' });
        const button = item.querySelector('[data-helpful] span');
        if (button) button.textContent = payload.helpful_count;
      } catch (error) { HF.toast(error.message, 'error'); }
    }
  });

  document.querySelector('#review-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const message = document.querySelector('#review-form-message');
    const files = [...(form.elements.media.files || [])];
    const invalid = files.map(HF.fileIsAllowed).find((result) => !result.ok);
    if (invalid) { message.textContent = invalid.message; message.className = 'form-message error'; return; }
    message.textContent = 'Saving your review…'; message.className = 'form-message';
    try {
      const payload = await HF.request(editingReviewId ? `/api/reviews/${editingReviewId}` : `/api/hostels/${page.dataset.hostelId}/reviews`, { method: editingReviewId ? 'PUT' : 'POST', body: new FormData(form) });
      message.textContent = 'Saved — refreshing the review summary.'; message.className = 'form-message success';
      hostel = payload.hostel;
      resetReviewForm(); renderGallery(); renderReviews(); renderSummary();
    } catch (error) { message.textContent = error.message; message.className = 'form-message error'; }
  });
  document.querySelector('#cancel-review-edit')?.addEventListener('click', resetReviewForm);
  document.querySelector('#share-hostel')?.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(window.location.href); HF.toast('Link copied to your clipboard.', 'success'); } catch (_) { HF.toast('Copy the page URL to share this stay.', 'info'); }
  });

  const mapElement = document.querySelector('#mini-map');
  if (mapElement && window.L) {
    const map = L.map(mapElement, { zoomControl: false, attributionControl: false }).setView([hostel.latitude, hostel.longitude], 15);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
    L.marker([hostel.latitude, hostel.longitude], { icon: L.divIcon({ className: '', html: '<span class="college-marker">⌂</span>', iconSize: [35, 35], iconAnchor: [17, 17] }) }).addTo(map);
    L.circle([hostel.latitude, hostel.longitude], { radius: 180, color: '#3567e8', weight: 1, fillColor: '#3567e8', fillOpacity: .09 }).addTo(map);
  }
  renderGallery(); renderReviews();
})();
