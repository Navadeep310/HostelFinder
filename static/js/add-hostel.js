(() => {
  const form = document.querySelector('#add-hostel-form');
  const mapElement = document.querySelector('#listing-map');
  if (!form || !mapElement) return;
  const latitude = document.querySelector('#latitude');
  const longitude = document.querySelector('#longitude');
  const mapMessage = document.querySelector('#map-message');
  let pin;

  const map = window.L ? L.map(mapElement).setView([17.43, 78.44], 11) : null;
  if (map) {
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
    map.on('click', (event) => {
      const { lat, lng } = event.latlng;
      latitude.value = lat.toFixed(6); longitude.value = lng.toFixed(6);
      mapMessage.textContent = `Pin set at ${lat.toFixed(5)}, ${lng.toFixed(5)}. You can click again to move it.`;
      mapMessage.className = 'form-message success';
      if (pin) pin.setLatLng(event.latlng); else pin = L.marker(event.latlng).addTo(map);
    });
  }

  fetch('/api/colleges').then((response) => response.json()).then((payload) => {
    const select = document.querySelector('#nearby-college');
    (payload.colleges || []).forEach((college) => {
      const option = document.createElement('option'); option.value = college.id; option.textContent = `${college.short_name} · ${college.area}`; select.appendChild(option);
    });
  }).catch(() => {});

  const mediaInput = document.querySelector('#listing-media');
  mediaInput?.addEventListener('change', () => {
    const preview = document.querySelector('#media-preview'); preview.innerHTML = '';
    const files = [...mediaInput.files];
    if (files.length > 8) { HF.toast('You can add up to 8 files.', 'error'); mediaInput.value = ''; return; }
    for (const file of files) {
      const result = HF.fileIsAllowed(file);
      if (!result.ok) { HF.toast(result.message, 'error'); mediaInput.value = ''; preview.innerHTML = ''; return; }
      const item = document.createElement('div'); item.className = 'media-preview-item';
      if (result.type === 'image') { const image = document.createElement('img'); image.src = URL.createObjectURL(file); image.alt = file.name; item.appendChild(image); }
      else item.innerHTML = '<span>▶ Video<br>preview</span>';
      preview.appendChild(item);
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = document.querySelector('#listing-message');
    if (!latitude.value || !longitude.value) { message.textContent = 'Click the map to set the property location.'; message.className = 'form-message error'; mapMessage.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
    const files = [...(mediaInput?.files || [])];
    const invalid = files.map(HF.fileIsAllowed).find((result) => !result.ok);
    if (invalid) { message.textContent = invalid.message; message.className = 'form-message error'; return; }
    const submit = form.querySelector('button[type="submit"]'); submit.disabled = true; submit.textContent = 'Submitting…'; message.textContent = '';
    try {
      const payload = await HF.request('/api/hostels', { method: 'POST', body: new FormData(form) });
      message.textContent = payload.message; message.className = 'form-message success';
      form.reset(); document.querySelector('#media-preview').innerHTML = '';
      window.setTimeout(() => { window.location.href = '/'; }, 1800);
    } catch (error) { message.textContent = error.message; message.className = 'form-message error'; submit.disabled = false; submit.innerHTML = 'Submit for approval <span>→</span>'; }
  });
})();
