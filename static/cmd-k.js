/* curiosity — Cmd+K command palette */
(function() {
  var overlay = document.getElementById('cmd-k-overlay');
  var modal = document.getElementById('cmd-k-modal');
  var input = document.getElementById('cmd-k-input');
  var results = document.getElementById('cmd-k-results');
  var trigger = document.getElementById('cmd-k-trigger');
  if (!overlay || !input) return;

  var debounceTimer;
  var commandsHTML = results.innerHTML;
  var selectedIndex = -1;

  function open() {
    overlay.classList.add('open');
    input.value = '';
    input.focus();
    selectedIndex = -1;
    // Show recent saves when opened with no query
    fetch('/api/search?q=&recent=5')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (input.value.trim()) return; // user already typed
        var html = '';
        if (data.bookmarks && data.bookmarks.length) {
          html += '<div class="cmd-k-section"><div class="cmd-k-section-label">Recent</div>';
          data.bookmarks.slice(0, 5).forEach(function(b) {
            html += '<a href="/item/' + b.id + '" class="cmd-k-item">' +
              '<span class="cmd-k-item-title">' + esc(b.title || 'Untitled') + '</span>' +
              '<span class="cmd-k-item-meta">' + esc(b.domain || '') + '</span></a>';
          });
          html += '</div>';
        }
        html += commandsHTML;
        results.innerHTML = html;
        bindActions();
      })
      .catch(function() {
        results.innerHTML = commandsHTML;
        bindActions();
      });
  }

  function close() {
    overlay.classList.remove('open');
    input.value = '';
    selectedIndex = -1;
  }

  // Open on Cmd+K or trigger click
  document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      overlay.classList.contains('open') ? close() : open();
    }
    // / to open when not in an input
    if (e.key === '/' && !e.target.matches('input, textarea, select') && !overlay.classList.contains('open')) {
      e.preventDefault();
      open();
    }
  });

  if (trigger) trigger.addEventListener('click', open);

  // Close on overlay click (not modal)
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) close();
  });

  // Keyboard navigation inside palette
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
      return;
    }

    var items = results.querySelectorAll('.cmd-k-item');

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
      updateSelection(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      updateSelection(items);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      var target = selectedIndex >= 0 ? items[selectedIndex] : items[0];
      if (target) {
        if (target.href) {
          window.location.href = target.href;
          close();
        } else {
          target.click();
        }
      }
    }
  });

  function updateSelection(items) {
    items.forEach(function(el) { el.classList.remove('selected'); });
    if (selectedIndex >= 0 && selectedIndex < items.length) {
      items[selectedIndex].classList.add('selected');
      items[selectedIndex].scrollIntoView({ block: 'nearest' });
    }
  }

  // Search as you type
  input.addEventListener('input', function() {
    var q = this.value.trim();
    clearTimeout(debounceTimer);
    selectedIndex = -1;

    if (!q) {
      results.innerHTML = commandsHTML;
      bindActions();
      return;
    }

    // URL detection
    if (q.match(/^https?:\/\//)) {
      results.innerHTML =
        '<div class="cmd-k-section">' +
        '<div class="cmd-k-section-label">Actions</div>' +
        '<button class="cmd-k-item" data-action="ingest" data-url="' + esc(q) + '">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>' +
        'Save this URL to your library' +
        '</button></div>';
      bindActions();
      return;
    }

    debounceTimer = setTimeout(function() {
      results.innerHTML = '<div class="cmd-k-section"><div class="cmd-k-section-label">Searching...</div>' +
        '<div style="padding: 8px 16px;"><div class="skeleton-line" style="width:70%;margin-bottom:10px;"></div>' +
        '<div class="skeleton-line" style="width:50%;"></div></div></div>';
      fetch('/api/search?q=' + encodeURIComponent(q))
        .then(function(r) { return r.json(); })
        .then(function(data) {
          var html = '';

          if (data.bookmarks && data.bookmarks.length) {
            html += '<div class="cmd-k-section"><div class="cmd-k-section-label">Bookmarks</div>';
            data.bookmarks.slice(0, 6).forEach(function(b) {
              html += '<a href="/item/' + b.id + '" class="cmd-k-item">' +
                '<span class="cmd-k-item-title">' + esc(b.title || 'Untitled') + '</span>' +
                '<span class="cmd-k-item-meta">' + esc(b.domain || '') + '</span></a>';
            });
            html += '</div>';
          }

          if (data.notes && data.notes.length) {
            html += '<div class="cmd-k-section"><div class="cmd-k-section-label">Notes</div>';
            data.notes.slice(0, 3).forEach(function(n) {
              html += '<a href="/item/note:' + n.id + '" class="cmd-k-item">' +
                '<span class="cmd-k-item-title">' + esc((n.snippet || n.content || '').substring(0, 80)) + '</span></a>';
            });
            html += '</div>';
          }

          html += commandsHTML;

          if (!data.bookmarks?.length && !data.notes?.length) {
            html = '<div class="cmd-k-section"><div class="cmd-k-empty">Nothing found for "' + esc(q) + '"</div></div>' + commandsHTML;
          }

          results.innerHTML = html;
          selectedIndex = -1;
          bindActions();
        });
    }, 200);
  });

  // Action handlers
  function bindActions() {
    results.querySelectorAll('[data-action]').forEach(function(el) {
      el.addEventListener('click', function(e) {
        var action = this.dataset.action;
        if (action === 'navigate') {
          close();
        } else if (action === 'ingest') {
          e.preventDefault();
          var url = this.dataset.url;
          fetch('/api/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
          }).then(function(r) { return r.json(); })
          .then(function(data) {
            close();
            var t = document.createElement('div');
            t.className = 'toast';
            t.textContent = data.status === 'exists' ? 'Already saved' : 'Saved: ' + (data.title || url).substring(0, 60);
            document.body.appendChild(t);
            setTimeout(function() { t.remove(); }, 3000);
          });
        } else if (action === 'toggle-theme') {
          e.preventDefault();
          var doc = document.documentElement;
          var isDark = doc.getAttribute('data-theme') === 'dark';
          if (isDark) {
            doc.removeAttribute('data-theme');
            localStorage.setItem('curiosity-theme', 'light');
          } else {
            doc.setAttribute('data-theme', 'dark');
            localStorage.setItem('curiosity-theme', 'dark');
          }
          close();
        }
      });
    });
  }

  function esc(s) {
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  bindActions();
})();
