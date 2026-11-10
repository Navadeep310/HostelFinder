(() => {
  const call = async (url, options) => {
    try { return await HF.request(url, options); } catch (error) { HF.toast(error.message, 'error'); throw error; }
  };
  document.querySelectorAll('[data-hostel-id] [data-status]').forEach((button) => {
    button.addEventListener('click', async () => {
      const row = button.closest('[data-hostel-id]');
      const id = row.dataset.hostelId;
      button.disabled = true;
      try { await call(`/api/admin/hostels/${id}/status`, { method: 'POST', body: JSON.stringify({ status: button.dataset.status }) }); row.remove(); HF.toast(`Listing ${button.dataset.status}.`, 'success'); } catch (_) { button.disabled = false; }
    });
  });
  document.querySelectorAll('[data-remove-review]').forEach((button) => {
    button.addEventListener('click', async () => {
      const row = button.closest('[data-review-id]');
      if (!window.confirm('Remove this review from public view?')) return;
      try { await call(`/api/admin/reviews/${row.dataset.reviewId}`, { method: 'DELETE' }); row.remove(); HF.toast('Review removed.', 'success'); } catch (_) {}
    });
  });
  document.querySelectorAll('[data-remove-media]').forEach((button) => {
    button.addEventListener('click', async () => {
      const row = button.closest('[data-media-id]');
      if (!window.confirm('Remove this media item?')) return;
      try { await call(`/api/admin/media/${row.dataset.mediaId}`, { method: 'DELETE' }); row.remove(); HF.toast('Media removed.', 'success'); } catch (_) {}
    });
  });
})();
