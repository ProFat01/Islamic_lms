/* Islamic LMS — main.js */

// ── Theme Toggle ─────────────────────────────────
(function () {
  const STORAGE_KEY = 'lms-theme';
  const btn = document.getElementById('theme-toggle');
  const icon = document.getElementById('theme-icon');

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
  }

  // Load saved theme or system preference
  const saved = localStorage.getItem(STORAGE_KEY);
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(saved || (prefersDark ? 'dark' : 'light'));

  if (btn) {
    btn.addEventListener('click', function () {
      const current = document.documentElement.getAttribute('data-theme');
      applyTheme(current === 'dark' ? 'light' : 'dark');
    });
  }
})();

// ── Mobile Nav Toggle ─────────────────────────────
(function () {
  const hamburger = document.getElementById('hamburger');
  const navLinks  = document.getElementById('nav-links');

  if (hamburger && navLinks) {
    hamburger.addEventListener('click', function () {
      navLinks.classList.toggle('open');
      hamburger.setAttribute('aria-expanded',
        navLinks.classList.contains('open') ? 'true' : 'false'
      );
    });

    // Close nav on link click (mobile)
    navLinks.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        navLinks.classList.remove('open');
      });
    });
  }
})();

// ── Auto-dismiss Alerts ───────────────────────────
(function () {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(function (alert) {
    // Click to dismiss
    alert.addEventListener('click', function () {
      alert.style.opacity = '0';
      alert.style.transform = 'translateX(30px)';
      setTimeout(function () { alert.remove(); }, 300);
    });
    // Auto dismiss after 5s
    setTimeout(function () {
      if (alert.parentNode) {
        alert.style.transition = 'opacity .4s, transform .4s';
        alert.style.opacity = '0';
        alert.style.transform = 'translateX(30px)';
        setTimeout(function () {
          if (alert.parentNode) alert.remove();
        }, 400);
      }
    }, 5000);
  });
})();

// ── Video URL → Embed converter ───────────────────
// Used in lesson view to convert YouTube/Vimeo URLs
function getEmbedUrl(url) {
  if (!url) return null;

  // YouTube
  let match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\s]+)/);
  if (match) return 'https://www.youtube.com/embed/' + match[1];

  // Vimeo
  match = url.match(/vimeo\.com\/(\d+)/);
  if (match) return 'https://player.vimeo.com/video/' + match[1];

  // Already an embed URL or other
  return url;
}

// Apply embed conversion on lesson pages
(function () {
  const container = document.getElementById('video-container');
  const rawUrl = document.getElementById('video-raw-url');
  if (container && rawUrl) {
    const embed = getEmbedUrl(rawUrl.value);
    if (embed) {
      const iframe = document.createElement('iframe');
      iframe.src = embed;
      iframe.allowFullscreen = true;
      iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
      container.appendChild(iframe);
      container.style.display = 'block';
    }
  }
})();

// ── Active Nav Link ───────────────────────────────
(function () {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(function (link) {
    if (link.getAttribute('href') === path) {
      link.classList.add('active');
    }
  });
})();

// ── Confirm Delete ────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(function (el) {
  el.addEventListener('click', function (e) {
    if (!confirm(el.getAttribute('data-confirm'))) {
      e.preventDefault();
    }
  });
});
