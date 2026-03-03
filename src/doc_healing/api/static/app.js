/* ===== OASIS — Sidebar Navigation + Real Live Demo ===== */

// Page switching via sidebar links
const sidebarLinks = document.querySelectorAll('.sidebar-link');
const pages = document.querySelectorAll('.page');
const breadcrumb = document.getElementById('breadcrumb');

function showPage(pageId) {
    pages.forEach(p => p.classList.add('hidden'));
    sidebarLinks.forEach(l => l.classList.remove('active'));

    const target = document.getElementById('page-' + pageId);
    if (target) {
        target.classList.remove('hidden');
        window.scrollTo(0, 0);
        const h1 = target.querySelector('h1');
        if (h1) breadcrumb.textContent = h1.textContent.split('—')[0].trim();
    }

    document.querySelectorAll(`[data-page="${pageId}"]`).forEach(l => l.classList.add('active'));
}

// Click handler for all data-page links (sidebar + inline)
document.addEventListener('click', (e) => {
    const link = e.target.closest('[data-page]');
    if (link) {
        e.preventDefault();
        showPage(link.dataset.page);
    }
});

// ===== Live Demo — Calls the REAL backend /api/analyze endpoint =====
const analyzeBtn = document.getElementById('analyzeBtn');
const demoCode = document.getElementById('demoCode');
const demoLang = document.getElementById('demoLang');
const demoOutput = document.getElementById('demoOutput');

// Preset example buttons
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.preset-btn');
    if (btn && demoCode && demoLang) {
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        demoCode.value = btn.dataset.code;
        demoLang.value = btn.dataset.lang;
        if (demoOutput) demoOutput.innerHTML = '<p class="placeholder">Click <strong>Analyze Code</strong> to see results.</p>';
    }
});

if (analyzeBtn) {
    analyzeBtn.addEventListener('click', async () => {
        const code = demoCode.value.trim();
        const lang = demoLang.value;

        if (!code) {
            demoOutput.innerHTML = '<p class="placeholder">Please enter some code first.</p>';
            return;
        }

        // Show loading state
        analyzeBtn.textContent = '⏳ Analyzing...';
        analyzeBtn.disabled = true;
        demoOutput.innerHTML = '<p class="placeholder">Running OASIS static analyzer...</p>';

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: code, language: lang })
            });

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const result = await response.json();
            renderResult(result);
        } catch (err) {
            demoOutput.innerHTML = `<div class="output-error"><strong>Error</strong>: Could not reach the OASIS backend — ${err.message}</div>`;
        } finally {
            analyzeBtn.textContent = '🔍 Analyze Code';
            analyzeBtn.disabled = false;
        }
    });
}

function renderResult(result) {
    if (!result.has_issues || result.errors.length === 0) {
        demoOutput.innerHTML = '<div class="output-success">✅ No issues detected — code looks good!</div>';
        return;
    }

    const langNote = `<p style="color:#888;font-size:0.82rem;margin-bottom:10px;">Detected language: <strong>${result.language}</strong></p>`;

    const errorHtml = result.errors.map(e => {
        const errType = e.type || 'Error';
        const errMsg = e.message || e.detail || JSON.stringify(e);
        const isWarning = errType.includes('Warning');
        const cls = isWarning ? 'output-warning' : 'output-error';
        return `<div class="${cls}"><strong>${errType}</strong>: ${errMsg}</div>`;
    }).join('');

    demoOutput.innerHTML = `
    <div class="output-result">
      <h4>🏜️ OASIS Analysis — ${result.errors.length} issue(s) found</h4>
      ${langNote}
      ${errorHtml}
    </div>`;
}
