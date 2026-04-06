/* curiosity — Global search + voice input */

(function() {
  const input = document.getElementById('search-input');
  if (!input) return;

  const dropdown = document.getElementById('search-dropdown');
  const micBtn = document.getElementById('search-mic');
  let debounceTimer = null;
  let recognition = null;

  // Search as you type
  input.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    const q = this.value.trim();
    if (q.length < 2) { hideDropdown(); return; }

    // URL detection
    if (q.match(/^https?:\/\//)) {
      showUrlAction(q);
      return;
    }

    debounceTimer = setTimeout(() => doSearch(q), 200);
  });

  // Shift+Enter to save note
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.shiftKey) {
      e.preventDefault();
      saveNote(this.value.trim());
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const q = this.value.trim();
      if (q.length >= 2) {
        window.location.href = '/library?q=' + encodeURIComponent(q);
      }
    } else if (e.key === 'Escape') {
      this.value = '';
      hideDropdown();
      this.blur();
    }
  });

  // Click outside to close
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.search-container')) hideDropdown();
  });

  // Voice input
  if (micBtn && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    micBtn.addEventListener('click', function() {
      if (micBtn.classList.contains('listening')) {
        recognition.stop();
        micBtn.classList.remove('listening');
      } else {
        recognition.start();
        micBtn.classList.add('listening');
      }
    });

    recognition.onresult = function(event) {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      input.value = transcript;
      input.dispatchEvent(new Event('input'));
    };

    recognition.onend = function() {
      micBtn.classList.remove('listening');
    };

    recognition.onerror = function() {
      micBtn.classList.remove('listening');
    };
  } else if (micBtn) {
    micBtn.style.display = 'none';
  }

  async function doSearch(q) {
    try {
      const resp = await fetch('/api/search?q=' + encodeURIComponent(q));
      const data = await resp.json();
      renderResults(data, q);
    } catch (err) {
      console.error('Search error:', err);
    }
  }

  function renderResults(data, q) {
    if (!dropdown) return;
    let html = '';

    if (data.bookmarks && data.bookmarks.length) {
      html += '<div class="search-group-label">Bookmarks</div>';
      data.bookmarks.slice(0, 8).forEach(b => {
        const title = b.title || b.url || 'Untitled';
        html += `<a href="/item/${b.id}" class="search-result-item">
          <span class="badge badge-bookmark">B</span>
          <span class="title">${escHtml(title)}</span>
          <span class="domain">${escHtml(b.domain || '')}</span>
        </a>`;
      });
    }

    if (data.notes && data.notes.length) {
      html += '<div class="search-group-label">Notes</div>';
      data.notes.slice(0, 5).forEach(n => {
        const preview = (n.content || '').substring(0, 80);
        html += `<a href="/item/note:${n.id}" class="search-result-item">
          <span class="badge badge-note">N</span>
          <span class="title">${escHtml(preview)}</span>
        </a>`;
      });
    }

    if (data.lessons && data.lessons.length) {
      html += '<div class="search-group-label">Lessons</div>';
      data.lessons.slice(0, 5).forEach(l => {
        const preview = (l.lesson || '').substring(0, 80);
        html += `<div class="search-result-item">
          <span class="badge badge-lesson">L</span>
          <span class="title">${escHtml(preview)}</span>
          <span class="domain">${escHtml(l.date || '')}</span>
        </div>`;
      });
    }

    if (!html) {
      html = `<div class="search-hint">No results for "${escHtml(q)}"</div>`;
    }

    html += `<div class="search-hint">Shift+Enter to save as note</div>`;

    dropdown.innerHTML = html;
    dropdown.classList.add('active');
  }

  function showUrlAction(url) {
    if (!dropdown) return;
    dropdown.innerHTML = `
      <div class="search-action" onclick="ingestUrl('${escHtml(url)}')">
        + Ingest this URL
      </div>
      <div class="search-hint">Save to curiosity for AI enrichment</div>
    `;
    dropdown.classList.add('active');
  }

  function hideDropdown() {
    if (dropdown) dropdown.classList.remove('active');
  }

  async function saveNote(content) {
    if (!content) return;
    try {
      const resp = await fetch('/api/note', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, source: 'search_bar' }),
      });
      const data = await resp.json();
      if (data.id) {
        input.value = '';
        hideDropdown();
        showToast('Note saved');
      }
    } catch (err) {
      showToast('Failed to save note');
    }
  }

  // Global function for URL ingestion
  window.ingestUrl = async function(url) {
    try {
      const resp = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();
      if (data.status === 'exists') {
        showToast('Already in library');
      } else {
        showToast('URL saved — AI will enrich next session');
      }
      input.value = '';
      hideDropdown();
    } catch (err) {
      showToast('Failed to ingest URL');
    }
  };

  function showToast(msg) {
    let toast = document.querySelector('.toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'toast';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2500);
  }

  function escHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  // Keyboard shortcut: / to focus search
  document.addEventListener('keydown', function(e) {
    if (e.key === '/' && !e.target.matches('input, textarea')) {
      e.preventDefault();
      input.focus();
    }
  });
})();
