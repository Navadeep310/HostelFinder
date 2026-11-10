(() => {
  const root = document.documentElement;
  const themeButton = document.querySelector('#theme-toggle');
  const savedTheme = localStorage.getItem('hostelfinder-theme');
  if (savedTheme === 'dark' || savedTheme === 'light') root.dataset.theme = savedTheme;
  const updateThemeButton = () => {
    if (!themeButton) return;
    const dark = root.dataset.theme === 'dark';
    themeButton.textContent = dark ? '☀' : '☾';
    themeButton.title = dark ? 'Use light mode' : 'Use dark mode';
    themeButton.setAttribute('aria-label', themeButton.title);
  };
  updateThemeButton();
  themeButton?.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('hostelfinder-theme', root.dataset.theme);
    updateThemeButton();
  });

  document.querySelectorAll('.flash-close').forEach((button) => {
    button.addEventListener('click', () => button.closest('.flash')?.remove());
  });

  window.HF = {
    csrf: () => document.querySelector('meta[name="csrf-token"]')?.content || '',
    user: () => window.HOSTELFINDER?.user || null,
    escape(value) {
      return String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
    },
    toast(message, kind = 'info') {
      const region = document.querySelector('#toast-region');
      if (!region) return;
      const toast = document.createElement('div');
      toast.className = `toast ${kind}`;
      toast.textContent = message;
      region.appendChild(toast);
      window.setTimeout(() => toast.remove(), 4200);
    },
    async request(url, options = {}) {
      const headers = new Headers(options.headers || {});
      headers.set('X-CSRFToken', HF.csrf());
      if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
      const response = await fetch(url, { ...options, headers });
      let payload = {};
      try { payload = await response.json(); } catch (_) { payload = {}; }
      if (!response.ok) throw new Error(payload.error || `Request failed (${response.status}).`);
      return payload;
    },
    stars(rating) {
      const value = Number(rating) || 0;
      return `<span class="stars" aria-label="${value} out of 5 stars">${'★'.repeat(Math.round(value))}${'☆'.repeat(5 - Math.round(value))}</span>`;
    },
    fileIsAllowed(file) {
      const extension = file.name.split('.').pop()?.toLowerCase();
      const image = ['jpg', 'jpeg', 'png', 'webp'].includes(extension);
      const video = ['mp4', 'webm'].includes(extension);
      const limit = image ? 5 * 1024 * 1024 : 50 * 1024 * 1024;
      if ((!image && !video) || file.size <= 0 || file.size > limit) return { ok: false, message: `${file.name}: use JPG, PNG, WEBP (5 MB) or MP4, WEBM (50 MB).` };
      return { ok: true, type: image ? 'image' : 'video' };
    },
  };
})();
