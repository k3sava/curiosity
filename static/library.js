/* curiosity — Library view toggle + PDF upload */

(function() {
  const container = document.getElementById('library-container');
  const btnCards = document.getElementById('view-cards');
  const btnList = document.getElementById('view-list');
  const pdfInput = document.getElementById('pdf-upload');

  // --- View toggle ---
  if (container && btnCards && btnList) {
    var saved = localStorage.getItem('curiosity-library-view') || 'cards';
    setView(saved);

    btnCards.addEventListener('click', function() { setView('cards'); });
    btnList.addEventListener('click', function() { setView('list'); });
  }

  function setView(mode) {
    if (!container) return;
    if (mode === 'list') {
      container.className = 'library-view library-list';
      btnCards.classList.remove('active');
      btnList.classList.add('active');
    } else {
      container.className = 'library-view library-cards';
      btnCards.classList.add('active');
      btnList.classList.remove('active');
      mode = 'cards';
    }
    localStorage.setItem('curiosity-library-view', mode);
  }

  // --- PDF upload ---
  if (pdfInput) {
    pdfInput.addEventListener('change', async function() {
      var file = this.files[0];
      if (!file) return;

      if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast('Only PDF files are supported');
        return;
      }

      var formData = new FormData();
      formData.append('file', file);

      showToast('Uploading ' + file.name + '...');

      try {
        var resp = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });
        var data = await resp.json();

        if (data.error) {
          showToast(data.error);
        } else {
          showToast('Uploaded: ' + data.title + ' (' + data.word_count + ' words)');
          setTimeout(function() { location.reload(); }, 1500);
        }
      } catch (err) {
        showToast('Upload failed');
      }

      // Reset the input so the same file can be re-uploaded
      this.value = '';
    });
  }

  // --- Image upload (OCR) ---
  var imgInput = document.getElementById('image-upload');
  if (imgInput) {
    imgInput.addEventListener('change', async function() {
      var file = this.files[0];
      if (!file) return;

      var formData = new FormData();
      formData.append('file', file);

      showToast('Uploading ' + file.name + '...');

      try {
        var resp = await fetch('/api/upload-image', {
          method: 'POST',
          body: formData,
        });
        var data = await resp.json();

        if (data.error) {
          showToast(data.error);
        } else {
          var msg = 'Uploaded: ' + data.title;
          if (data.word_count > 0) msg += ' (' + data.word_count + ' words extracted)';
          if (!data.ocr_available) msg += ' (install pytesseract for OCR)';
          showToast(msg);
          setTimeout(function() { location.reload(); }, 1500);
        }
      } catch (err) {
        showToast('Upload failed');
      }

      this.value = '';
    });
  }

  function showToast(msg) {
    var toast = document.querySelector('.toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'toast';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(function() { toast.classList.remove('show'); }, 3000);
  }
})();
