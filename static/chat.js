/* curiosity — Chat / Q&A interface */

(function() {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const messages = document.getElementById('chat-messages');
  if (!form || !input || !messages) return;

  form.addEventListener('submit', function(e) {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    sendQuestion(q);
    input.value = '';
  });

  async function sendQuestion(question) {
    // Append user message
    appendMsg(question, 'user');

    // Show typing indicator
    const typing = appendMsg('Searching...', 'system');
    typing.classList.add('chat-typing');

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      const data = await resp.json();

      // Remove typing indicator
      typing.remove();

      if (data.error) {
        appendMsg(data.error, 'system');
        return;
      }

      // Build response HTML
      let html = '<div class="chat-answer">' + escHtml(data.answer) + '</div>';

      if (data.sources && data.sources.length) {
        html += '<div class="chat-sources">';
        data.sources.forEach(function(s) {
          html += '<a href="/item/' + s.id + '" class="chat-source-card">';
          html += '<div class="chat-source-title">' + escHtml(s.title) + '</div>';
          html += '<div class="chat-source-meta">';
          html += '<span>' + escHtml(s.domain) + '</span>';
          if (s.learning_value === 'high') {
            html += ' <span class="badge-high">high value</span>';
          }
          html += '</div>';
          if (s.insight) {
            html += '<div class="chat-source-insight">' + escHtml(s.insight) + '</div>';
          } else if (s.summary) {
            html += '<div class="chat-source-insight">' + escHtml(s.summary) + '</div>';
          }
          html += '</a>';
        });
        html += '</div>';
      }

      appendHtml(html, 'system');
    } catch (err) {
      typing.remove();
      appendMsg('Something went wrong. Try again.', 'system');
    }
  }

  function appendMsg(text, role) {
    const wrapper = document.createElement('div');
    wrapper.className = 'chat-msg chat-msg-' + role;
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble chat-bubble-' + role;
    bubble.textContent = text;
    wrapper.appendChild(bubble);
    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
    return wrapper;
  }

  function appendHtml(html, role) {
    const wrapper = document.createElement('div');
    wrapper.className = 'chat-msg chat-msg-' + role;
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble chat-bubble-' + role;
    bubble.innerHTML = html;
    wrapper.appendChild(bubble);
    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
    return wrapper;
  }

  function escHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }
})();
