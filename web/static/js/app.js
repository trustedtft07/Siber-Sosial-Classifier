/**
 * Siber Sosial - Cognitive Domain Hoax Classifier
 * Frontend Controller
 * Peran: Orang 3 (Frontend Architecture & Client Logic)
 */

const PRESETS = {
  1: {
    text: "Penerimaan Calon Bintara PK TNI AD 2026 membuka kuota jalur kilat dengan biaya administrasi via transfer rekening perorangan. Diteruskan berkali-kali! Sebarkan sebelum kuota habis!",
    url: "https://rekrutmen-tni-jalurkhusus.xyz/daftar"
  },
  2: {
    text: "VIRAL DARURAT! Beredar video pergerakan puluhan tank dan kendaraan taktis TNI AD menuju istana. Dikabarkan ada rencana kudeta militer dan pengambilalihan kekuasaan! Tolong sebarluaskan sebelum dihapus aparat!",
    url: ""
  },
  3: {
    text: "TNI AD mengerahkan 169 prajurit melalui Kodam IX/Udayana dan Korem 161/Wira Sakti beserta dukungan kesehatan dan logistik untuk membantu korban erupsi Gunung Lewotobi di Flores Timur, NTT.",
    url: "https://nasional.kompas.com/read/2024/11/25/09475381/tni-ad-kerahkan-169-prajurit-bantu-korban-erupsi-gunung-lewotobi"
  }
};

let latestAnalysisData = null;
let cachedFactChecks = [];
let latestBatchItems = [];
const HISTORY_STORAGE_KEY = "siber_sosial_scan_history_v1";

// ============================================================================
// 1. TAB CONTROLLER & PRESETS
// ============================================================================

function switchTab(mode) {
  const btnSingle = document.getElementById("tab-single-btn");
  const btnBatch = document.getElementById("tab-batch-btn");
  const paneSingle = document.getElementById("pane-single");
  const paneBatch = document.getElementById("pane-batch");

  if (!btnSingle || !btnBatch || !paneSingle || !paneBatch) {
    if (typeof navigateToPage === "function") {
      navigateToPage(mode === "batch" ? "batch" : "analisis");
    }
    return;
  }

  if (mode === "single") {
    btnSingle.classList.add("active");
    btnBatch.classList.remove("active");
    paneSingle.classList.add("active");
    paneBatch.classList.remove("active");
  } else {
    btnBatch.classList.add("active");
    btnSingle.classList.remove("active");
    paneBatch.classList.add("active");
    paneSingle.classList.remove("active");
  }
}

function updateCharCount() {
  const inputText = document.getElementById("input-text");
  const countEl = document.getElementById("input-char-count");
  if (!inputText || !countEl) return;
  const len = inputText.value.length;
  countEl.textContent = `${len.toLocaleString("id-ID")} / 15.000 karakter`;
}

function setActivePreset(id) {
  document.querySelectorAll(".btn-sample[data-preset]").forEach(btn => {
    btn.classList.toggle("active", Number(btn.dataset.preset) === id);
  });
}

function clearInputFields() {
  const inputText = document.getElementById("input-text");
  const inputUrl = document.getElementById("input-url");
  if (inputText) inputText.value = "";
  if (inputUrl) inputUrl.value = "";
  setActivePreset(0);
  updateCharCount();
  if (inputText) inputText.focus();
}

function focusPanel(panelId, pulse = false) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
  if (pulse) {
    panel.classList.remove("panel-pulse");
    void panel.offsetWidth;
    panel.classList.add("panel-pulse");
    setTimeout(() => panel.classList.remove("panel-pulse"), 900);
  }
}

function loadPreset(id) {
  const p = PRESETS[id];
  if (!p) return;
  switchTab("single");
  setActivePreset(id);
  document.getElementById("input-text").value = p.text;
  document.getElementById("input-url").value = p.url;
  updateCharCount();
  analyzeContent();
}

// ============================================================================
// 2. Pemeriksaan Tunggal & Render Hasil
// ============================================================================

function updateProgressBar(barEl, percentage) {
  if (!barEl) return;
  const pct = Math.min(100, Math.max(0, percentage));
  barEl.style.width = `${pct}%`;

  barEl.classList.remove("fill-green", "fill-yellow", "fill-red");
  if (pct >= 70) {
    barEl.classList.add("fill-red");
  } else if (pct >= 45) {
    barEl.classList.add("fill-yellow");
  } else {
    barEl.classList.add("fill-green");
  }
}

async function analyzeContent() {
  const text = document.getElementById("input-text").value.trim();
  const url = document.getElementById("input-url").value.trim();

  if (!text && !url) {
    showToast("Masukkan teks narasi atau tautan URL berita yang ingin diverifikasi.", "info");
    return;
  }

  const btn = document.getElementById("btn-analyze");
  btn.disabled = true;
  btn.textContent = "Memeriksa...";

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text || null, url: url || null })
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || "Gagal memproses analisis narasi");
    }

    const data = await res.json();
    latestAnalysisData = data;
    renderAnalysis(data);
    saveToHistory(data, text || data.input_preview || url, url);
    showToast("Pemeriksaan selesai.", "success");
    if (window.matchMedia("(max-width: 960px)").matches) {
      focusPanel("result-panel", true);
    }
  } catch (err) {
    showToast(`Terjadi kesalahan: ${err.message}`, "info");
    console.error("Analysis Error:", err);
  } finally {
    btn.disabled = false;
    btn.textContent = "Periksa Konten";
  }
}

function renderAnalysis(data) {
  const risk = data.risk_assessment;
  const layers = data.layers;
  const xai = data.explainable_ai;

  // Skor utama & progress bar
  const scoreEl = document.getElementById("val-score");
  scoreEl.textContent = risk.score;

  const classBadge = document.getElementById("val-classification");
  classBadge.textContent = risk.classification;

  if (risk.score >= 70) {
    scoreEl.style.color = "#ef4444";
    classBadge.className = "badge-status-pill badge-danger";
  } else if (risk.score >= 45) {
    scoreEl.style.color = "#f59e0b";
    classBadge.className = "badge-status-pill badge-warning";
  } else {
    scoreEl.style.color = "#10b981";
    classBadge.className = "badge-status-pill badge-success";
  }

  updateProgressBar(document.getElementById("bar-overall"), risk.score);

  // Metadata Ancaman
  document.getElementById("val-domain").textContent = risk.threat_domain || "Netral / Terverifikasi";
  const actionEl = document.getElementById("val-action");
  if (actionEl) {
    actionEl.textContent = risk.action_code || "-";
  }

  // Sub-skor 3 lapisan
  const lingScore = risk.sub_scores.linguistic_score;
  const evidScore = risk.sub_scores.evidence_risk;
  const srcScore = risk.sub_scores.source_risk;

  document.getElementById("sub-linguistic").textContent = `${lingScore}%`;
  document.getElementById("sub-evidence").textContent = `${evidScore}%`;
  document.getElementById("sub-source").textContent = `${srcScore}%`;

  updateProgressBar(document.getElementById("bar-linguistic"), lingScore);
  updateProgressBar(document.getElementById("bar-evidence"), evidScore);
  updateProgressBar(document.getElementById("bar-source"), srcScore);

  // Detail indikator linguistik
  const lingBox = document.getElementById("box-linguistic");
  const lingTriggers = [
    ...(layers.linguistic.urgency_triggers || []),
    ...(layers.linguistic.conspiracy_triggers || []),
    ...(layers.linguistic.authority_triggers || []),
    ...(layers.linguistic.sara_triggers || []),
    ...(layers.linguistic.anonymous_claim_triggers || layers.linguistic.anonymous_claim_markers || [])
  ];

  let chipsHtml = "";
  if (lingTriggers.length > 0) {
    chipsHtml = `
      <div class="chips-container">
        ${lingTriggers.map(t => `<span class="badge-chip">${escapeHtml(t)}</span>`).join("")}
      </div>
    `;
  } else {
    chipsHtml = `<div class="chips-container"><span class="badge-chip badge-chip-green">Tidak ditemukan frasa provokasi</span></div>`;
  }

  lingBox.innerHTML = `
    <strong>Indikator Leksikal:</strong> ${chipsHtml}
    <div style="margin-top: 0.4rem; font-size: 0.78rem; color: #52525b;">
      <strong>Rasio Huruf Kapital:</strong> ${(layers.linguistic.caps_ratio * 100).toFixed(1)}% &bull; 
      <strong>Tanda Seru:</strong> ${layers.linguistic.exclamation_count} &bull; 
      <strong>Sensasional:</strong> ${layers.linguistic.is_sensational ? 'Ya' : 'Tidak'}
    </div>
  `;

  // Layer 2 Detail Bukti RAG
  const evidBox = document.getElementById("box-evidence");
  const contradictionHtml = (risk.fact_contradiction && risk.fact_contradiction_note)
    ? `<div style="margin-top: 0.4rem; color: #b91c1c; font-weight: 600;">Kontradiksi Fakta: ${escapeHtml(risk.fact_contradiction_note)}</div>`
    : "";

  if (risk.best_match && risk.best_match.similarity_score > 0.25) {
    const bm = risk.best_match;
    const isSalah = bm.verdict === 'SALAH';
    const isMisleading = bm.verdict === 'MISLEADING';
    const badgeClass = isSalah ? 'badge-danger' : isMisleading ? 'badge-warning' : 'badge-success';
    const refLinkHtml = bm.reference_url && /^https?:\/\//i.test(bm.reference_url)
      ? `<div><a href="${escapeHtml(bm.reference_url)}" target="_blank" rel="noopener noreferrer" class="ref-link-inline">Buka Sumber Klarifikasi</a></div>`
      : '';

    evidBox.innerHTML = `
      <strong>Arsip Rujukan Terdekat:</strong> [${escapeHtml(bm.id)}] ${escapeHtml(bm.source_agency)} (${escapeHtml(bm.date || '-')})<br>
      <strong>Status Vonis:</strong> <span class="badge ${badgeClass}">${escapeHtml(bm.verdict)}</span> &bull; 
      <strong>Kemiripan Kosinus:</strong> ${(bm.similarity_score * 100).toFixed(1)}%<br>
      <strong>Fakta Terverifikasi:</strong> ${escapeHtml(bm.fact)}
      ${refLinkHtml}
      ${contradictionHtml}
    `;
  } else {
    evidBox.innerHTML = `
      <strong>Status Bukti Fakta:</strong> Belum ada arsip klarifikasi yang cocok (&le; 25%). 
      <span style="color: #b45309; font-weight: 600;">Narasi baru belum tercatat di arsip rujukan.</span>
      ${contradictionHtml}
    `;
  }

  // Layer 3 Detail Sumber
  const srcBox = document.getElementById("box-source");
  const domainsStr = (layers.source.detected_domains && layers.source.detected_domains.length > 0)
    ? layers.source.detected_domains.join(", ")
    : "Tidak ada tautan eksplisit";

  let scrapeHtml = "";
  if (data.scraped_metadata) {
    if (data.scraped_metadata.title) {
      scrapeHtml = `<br><strong>Hasil Ekstraksi URL:</strong> ${escapeHtml(data.scraped_metadata.title)} (${data.scraped_metadata.word_count || 0} kata)`;
    } else if (data.scraped_metadata.error) {
      scrapeHtml = `<br><strong>Catatan Ekstraksi URL:</strong> ${escapeHtml(data.scraped_metadata.error)}`;
    }
  }

  srcBox.innerHTML = `
    <strong>Tier Sumber:</strong> <span class="badge badge-dark">${escapeHtml(layers.source.source_tier)}</span> &bull; 
    <strong>Domain:</strong> ${escapeHtml(domainsStr)}<br>
    <strong>Catatan Kredibilitas:</strong> ${escapeHtml(layers.source.notes || 'Normal')}
    ${scrapeHtml}
  `;

  // XAI & Rekomendasi
  document.getElementById("box-brief").textContent = xai.tactical_brief || "-";
  document.getElementById("box-recommendation").textContent = xai.counter_measure || "-";

  const factorsList = document.getElementById("list-factors");
  if (xai.key_factors && xai.key_factors.length > 0) {
    factorsList.innerHTML = xai.key_factors.map(f => `<li>${escapeHtml(f)}</li>`).join("");
  } else {
    factorsList.innerHTML = `<li>Tidak ditemukan indikator risiko signifikan.</li>`;
  }
}

// ============================================================================
// 3. Generator Laporan & Ekspor
// ============================================================================

function generateTacticalReportText(data) {
  if (!data) return "";
  const r = data.risk_assessment;
  const l = data.layers;
  const x = data.explainable_ai;
  const now = new Date().toLocaleString("id-ID", { timeZone: "Asia/Jakarta" });

  let text = `================================================================================\n`;
  text += `   LAPORAN VERIFIKASI KONTEN - SIBER SOSIAL\n`;
  text += `================================================================================\n`;
  text += `WAKTU ANALISIS       : ${now} WIB\n`;
  text += `SKOR RISIKO HOAKS    : ${r.score} / 100\n`;
  text += `KLASIFIKASI ANCAMAN  : ${r.classification}\n`;
  text += `DOMAIN ANCAMAN       : ${r.threat_domain || '-'}\n`;
  text += `KODE TINDAKAN        : ${r.action_code || '-'}\n`;
  text += `--------------------------------------------------------------------------------\n`;
  text += `PRATINJAU INPUT NARASI:\n"${data.input_preview || '-'}"\n`;
  text += `--------------------------------------------------------------------------------\n`;
  text += `PENILAIAN TIGA LAPISAN (THREE-LAYER HYBRID):\n`;
  text += `  1. Analisis Gaya Bahasa (Leksikon)  : ${r.sub_scores.linguistic_score}%\n`;
  text += `     - Sensasional: ${l.linguistic.is_sensational ? 'YA' : 'TIDAK'} | Rasio Kapital: ${(l.linguistic.caps_ratio * 100).toFixed(1)}% | Tanda Seru: ${l.linguistic.exclamation_count}\n`;
  text += `  2. Pencocokan Arsip Bukti (RAG)     : ${r.sub_scores.evidence_risk}%\n`;
  if (r.best_match && r.best_match.similarity_score > 0.25) {
    text += `     - Cocok dengan [${r.best_match.id}] (${r.best_match.source_agency}) - Status: ${r.best_match.verdict}\n`;
    text += `     - Fakta: ${r.best_match.fact}\n`;
  } else {
    text += `     - Status: Belum ada klarifikasi resmi yang cocok (Potensi Zero-Day Rumor)\n`;
  }
  text += `  3. Reputasi Sumber & Pola Sebaran   : ${r.sub_scores.source_risk}%\n`;
  text += `     - Tier: ${l.source.source_tier} | Catatan: ${l.source.notes}\n`;
  text += `--------------------------------------------------------------------------------\n`;
  text += `RINGKASAN ANALISIS:\n${x.tactical_brief}\n\n`;
  text += `FAKTOR RISIKO UTAMA:\n`;
  (x.key_factors || []).forEach((f, idx) => {
    text += `  ${idx + 1}. ${f}\n`;
  });
  text += `\nTINDAK LANJUT:\n${x.counter_measure}\n`;
  text += `================================================================================\n`;
  return text;
}

async function copyTacticalReport() {
  if (!latestAnalysisData) {
    showToast("Belum ada data analisis untuk disalin.", "info");
    return;
  }
  const report = generateTacticalReportText(latestAnalysisData);
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(report);
    } else {
      throw new Error("Clipboard API tidak tersedia");
    }
    showToast("Laporan berhasil disalin ke clipboard.", "success");
  } catch (err) {
    try {
      const ta = document.createElement("textarea");
      ta.value = report;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const copied = document.execCommand("copy");
      document.body.removeChild(ta);
      if (copied) {
        showToast("Laporan berhasil disalin ke clipboard.", "success");
        return;
      }
    } catch (_) {
      // Fall through to toast below
    }
    showToast("Gagal menyalin: Izin clipboard tidak diberikan.", "info");
  }
}

function downloadReport(format) {
  if (!latestAnalysisData) {
    showToast("Belum ada data analisis untuk diunduh.", "info");
    return;
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  let blob, filename;

  if (format === "json") {
    blob = new Blob([JSON.stringify(latestAnalysisData, null, 2)], { type: "application/json" });
    filename = `Laporan-Siber-Sosial-${timestamp}.json`;
  } else {
    const reportText = generateTacticalReportText(latestAnalysisData);
    blob = new Blob([reportText], { type: "text/plain;charset=utf-8" });
    filename = `Laporan-Verifikasi-${timestamp}.txt`;
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast(`Berkas ${filename} berhasil diunduh.`, "success");
}

// ============================================================================
// 4. Riwayat Lokal (LocalStorage)
// ============================================================================

function saveToHistory(analysisData, rawText, rawUrl = "") {
  try {
    let history = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY) || "[]");
    const displayText = rawText || rawUrl || "-";
    const entry = {
      timestamp: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
      rawText: rawText || "",
      rawUrl: rawUrl || "",
      preview: displayText.length > 55 ? displayText.substring(0, 52) + "..." : displayText,
      score: analysisData.risk_assessment.score,
      classification: analysisData.risk_assessment.classification,
      data: analysisData
    };

    // Sisipkan di awal, simpan maksimal 10 riwayat
    history.unshift(entry);
    if (history.length > 10) history = history.slice(0, 10);
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
    renderHistory();
  } catch (e) {
    console.error("Gagal menyimpan ke localStorage:", e);
  }
}

function renderHistory() {
  const listEl = document.getElementById("history-list");
  const emptyEl = document.getElementById("history-empty");
  if (!listEl) return;

  try {
    const history = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY) || "[]");
    if (history.length === 0) {
      if (emptyEl) emptyEl.style.display = "block";
      listEl.innerHTML = "";
      return;
    }

    if (emptyEl) emptyEl.style.display = "none";
    listEl.innerHTML = history.map((item, idx) => {
      let badgeClass = "badge-success";
      if (item.score >= 70) badgeClass = "badge-danger";
      else if (item.score >= 45) badgeClass = "badge-warning";

      return `
        <li class="history-item" data-history-index="${idx}">
          <span class="history-text" title="${escapeHtml(item.rawText || item.rawUrl || '')}">${escapeHtml(item.preview)}</span>
          <div class="history-meta">
            <span class="history-time">${escapeHtml(item.timestamp)}</span>
            <span class="history-reload-hint">Ketuk untuk muat</span>
            <span class="badge ${badgeClass}">${item.score}</span>
          </div>
        </li>
      `;
    }).join("");
  } catch (e) {
    console.error("Gagal merender riwayat:", e);
  }
}

function loadHistoryItem(idx) {
  try {
    const history = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY) || "[]");
    const item = history[idx];
    if (item && item.data) {
      document.getElementById("input-text").value = item.rawText || "";
      document.getElementById("input-url").value = item.rawUrl || "";
      setActivePreset(0);
      updateCharCount();
      latestAnalysisData = item.data;
      renderAnalysis(item.data);
      if (typeof navigateToPage === "function") {
        navigateToPage("analisis");
      }
      if (window.matchMedia("(max-width: 960px)").matches) {
        setTimeout(() => focusPanel("result-panel", true), 60);
      }
      showToast("Data riwayat dimuat ke lembar analisis.", "info");
    }
  } catch (e) {
    console.error("Gagal memuat item riwayat:", e);
  }
}

function clearHistory() {
  if (confirm("Hapus seluruh riwayat pemindaian lokal?")) {
    localStorage.removeItem(HISTORY_STORAGE_KEY);
    renderHistory();
    showToast("Riwayat lokal berhasil dibersihkan.", "info");
  }
}

// ============================================================================
// 5. Pencarian, Filter & Tambah Arsip
// ============================================================================

function syncCategoryFilterOptions() {
  const catFilter = document.getElementById("kb-filter-category");
  if (!catFilter) return;

  const existing = new Set(Array.from(catFilter.options).map(opt => opt.value));
  cachedFactChecks.forEach(item => {
    if (item.threat_category && !existing.has(item.threat_category)) {
      const opt = document.createElement("option");
      opt.value = item.threat_category;
      opt.textContent = item.threat_category;
      catFilter.appendChild(opt);
      existing.add(item.threat_category);
    }
  });
}

async function loadKnowledgeBase() {
  try {
    const res = await fetch("/api/fact-checks");
    if (!res.ok) throw new Error("Gagal mengambil data dari server");
    const json = await res.json();
    cachedFactChecks = json.data || [];
    syncCategoryFilterOptions();
    filterKnowledgeBase();
  } catch (e) {
    console.error("Gagal memuat arsip:", e);
    const tbody = document.getElementById("kb-tbody");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #ef4444;">Gagal memuat basis pengetahuan dari server.</td></tr>`;
    }
  }
}

function filterKnowledgeBase() {
  const searchInput = document.getElementById("kb-search");
  const catFilter = document.getElementById("kb-filter-category");
  const verdictFilter = document.getElementById("kb-filter-verdict");
  const counterEl = document.getElementById("kb-counter");
  const tbody = document.getElementById("kb-tbody");

  if (!tbody) return;

  const query = searchInput ? searchInput.value.toLowerCase().trim() : "";
  const selectedCat = catFilter ? catFilter.value : "";
  const selectedVerdict = verdictFilter ? verdictFilter.value : "";

  const filtered = cachedFactChecks.filter(item => {
    const matchQuery = !query || 
      (item.id && item.id.toLowerCase().includes(query)) ||
      (item.claim && item.claim.toLowerCase().includes(query)) ||
      (item.fact && item.fact.toLowerCase().includes(query)) ||
      (item.source_agency && item.source_agency.toLowerCase().includes(query));

    const matchCat = !selectedCat || item.threat_category === selectedCat;
    const matchVerdict = !selectedVerdict || item.verdict === selectedVerdict;

    return matchQuery && matchCat && matchVerdict;
  });

  if (counterEl) {
    counterEl.textContent = `Menampilkan ${filtered.length} dari ${cachedFactChecks.length} entri`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #9ca3af; padding: 1.5rem;">Tidak ditemukan arsip yang sesuai filter pencarian.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(item => {
    let badgeClass = "badge-success";
    if (item.verdict === "SALAH") badgeClass = "badge-danger";
    else if (item.verdict === "MISLEADING") badgeClass = "badge-warning";

    const safeRefUrl = item.reference_url && /^https?:\/\//i.test(item.reference_url)
      ? `<a href="${escapeHtml(item.reference_url)}" target="_blank" rel="noopener noreferrer" class="kb-ref-link">Tautan Rujukan</a>`
      : '';

    return `
      <tr class="kb-row-card">
        <td class="td-id"><code>${escapeHtml(item.id)}</code></td>
        <td class="td-cat"><span class="kb-cat-label">${escapeHtml(item.threat_category)}</span></td>
        <td class="td-main">
          <div class="kb-claim-text">${escapeHtml(item.claim)}</div>
          <div class="kb-fact-text"><strong>Fakta:</strong> ${escapeHtml(item.fact)}</div>
        </td>
        <td class="td-verdict"><span class="badge ${badgeClass}">${escapeHtml(item.verdict)}</span></td>
        <td class="td-source">
          <div class="kb-agency-name">${escapeHtml(item.source_agency)}</div>
          ${safeRefUrl}
        </td>
      </tr>
    `;
  }).join("");
}

function toggleAddFactCheckForm() {
  const formEl = document.getElementById("form-add-kb");
  const btnEl = document.getElementById("btn-toggle-add-kb");
  if (!formEl) return;

  const isHidden = formEl.style.display === "none" || !formEl.style.display;
  formEl.style.display = isHidden ? "block" : "none";
  if (btnEl) {
    btnEl.textContent = isHidden ? "Tutup Form" : "Tambah Entri";
  }
}

async function submitNewFactCheck(e) {
  e.preventDefault();
  const id = document.getElementById("fc-id").value.trim();
  const agency = document.getElementById("fc-agency").value.trim();
  const category = document.getElementById("fc-category").value;
  const verdict = document.getElementById("fc-verdict").value;
  const claim = document.getElementById("fc-claim").value.trim();
  const fact = document.getElementById("fc-fact").value.trim();
  const url = document.getElementById("fc-url").value.trim();

  const newEntry = {
    id: id || null,
    threat_category: category,
    claim,
    fact,
    verdict,
    source_agency: agency,
    reference_url: url,
    date: new Date().toISOString().split("T")[0]
  };

  const btnSave = document.getElementById("btn-save-fc");
  btnSave.disabled = true;
  btnSave.textContent = "Menyimpan...";

  try {
    const res = await fetch("/api/fact-checks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newEntry)
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || "Gagal menyimpan arsip klarifikasi ke server.");
    }

    const resJson = await res.json();
    const savedEntry = resJson.data || newEntry;

    const existingIdx = cachedFactChecks.findIndex(item => item.id === savedEntry.id);
    if (existingIdx >= 0) {
      cachedFactChecks[existingIdx] = savedEntry;
    } else {
      cachedFactChecks.unshift(savedEntry);
    }

    syncCategoryFilterOptions();
    filterKnowledgeBase();
    toggleAddFactCheckForm();
    e.target.reset();
    showToast(`Arsip ${savedEntry.id} berhasil ditambahkan ke basis data!`, "success");
  } catch (err) {
    showToast(`Gagal menyimpan: ${err.message}`, "info");
    console.error("Add FactCheck Error:", err);
  } finally {
    btnSave.disabled = false;
    btnSave.textContent = "Simpan";
  }
}

// ============================================================================
// 6. Pemindaian Massal (Batch)
// ============================================================================

const MAX_UPLOAD_BYTES = 512 * 1024;
const ALLOWED_UPLOAD_EXTS = new Set(["txt", "csv"]);
const BLOCKED_MULTI_EXTS = new Set([
  "exe", "dll", "bat", "cmd", "sh", "ps1", "php", "phtml", "phar",
  "py", "rb", "pl", "js", "mjs", "ts", "html", "htm", "svg", "jar",
  "vbs", "scr", "com", "jsp", "asp", "aspx", "cgi", "hta", "msi",
  "zip", "rar", "7z", "gz", "tar", "pdf"
]);

function hasBinaryMagicOrControlBytes(bytes) {
  const header = Array.from(bytes.slice(0, 8)).map(b => String.fromCharCode(b)).join("");
  if (
    header.startsWith("MZ") ||
    header.startsWith("\x7fELF") ||
    header.startsWith("%PDF-") ||
    header.startsWith("PK\x03\x04") ||
    header.startsWith("Rar!") ||
    header.startsWith("GIF8") ||
    header.startsWith("#!") ||
    (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) ||
    (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff)
  ) {
    return true;
  }
  for (let i = 0; i < bytes.length; i += 1) {
    const b = bytes[i];
    if ((b >= 0 && b <= 8) || b === 11 || b === 12 || (b >= 14 && b <= 31)) {
      return true;
    }
  }
  return false;
}

function setBatchDropzoneState(filename = "") {
  const dropzone = document.getElementById("batch-dropzone");
  const labelText = document.getElementById("batch-file-name");
  const clearBtn = document.getElementById("btn-clear-batch-file");
  if (!dropzone || !labelText) return;

  if (filename) {
    dropzone.classList.add("has-file");
    labelText.textContent = `Terpilih: ${filename}`;
    if (clearBtn) clearBtn.style.display = "inline-flex";
  } else {
    dropzone.classList.remove("has-file");
    labelText.textContent = "Pilih atau letakkan berkas .txt / .csv";
    if (clearBtn) clearBtn.style.display = "none";
  }
}

function clearBatchFile() {
  const input = document.getElementById("batch-file");
  if (input) input.value = "";
  setBatchDropzoneState("");
}

async function processBatchFile(file, inputEl = null) {
  if (!file) return;

  const resetInput = () => {
    if (inputEl) inputEl.value = "";
    setBatchDropzoneState("");
  };

  if (/[\\/\0]|\.\./.test(file.name) || file.name.length > 150) {
    showToast("Nama berkas tidak valid.", "info");
    resetInput();
    return;
  }

  const parts = file.name.toLowerCase().split(".");
  const ext = parts.length >= 2 ? parts[parts.length - 1] : "";
  const midExts = parts.slice(1, -1);
  if (!ALLOWED_UPLOAD_EXTS.has(ext) || midExts.some(p => BLOCKED_MULTI_EXTS.has(p))) {
    showToast("Format berkas ditolak. Hanya gunakan .txt atau .csv.", "info");
    resetInput();
    return;
  }

  if (file.size === 0) {
    showToast("Berkas kosong.", "info");
    resetInput();
    return;
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    showToast("Ukuran berkas melebihi batas maksimal 512 KB.", "info");
    resetInput();
    return;
  }

  try {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    if (hasBinaryMagicOrControlBytes(bytes)) {
      showToast("Berkas biner atau eksekutabel ditolak.", "info");
      resetInput();
      return;
    }

    const decoded = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (/<\s*(?:!doctype|html|script|svg|iframe|object|embed|\?php)\b/i.test(decoded)) {
      showToast("Berkas mengandung tag HTML atau skrip yang tidak diizinkan.", "info");
      resetInput();
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/api/analyze/batch/upload", {
      method: "POST",
      body: formData,
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(json.detail || "Berkas ditolak oleh server.");
    }

    document.getElementById("batch-text").value = json.text || "";
    setBatchDropzoneState(json.filename || file.name);
    showToast(`Berkas ${json.filename || file.name} dimuat (${json.entry_count} entri).`, "success");
  } catch (err) {
    showToast(err.message || "Berkas harus berupa teks UTF-8 yang valid.", "info");
    resetInput();
  }
}

async function handleBatchFileUpload(event) {
  const input = event.target;
  await processBatchFile(input.files[0], input);
}

function loadBatchItemDetail(idx) {
  const item = latestBatchItems[idx];
  if (!item || !item.analysisData) return;

  const inputText = document.getElementById("input-text");
  const inputUrl = document.getElementById("input-url");
  if (inputText) inputText.value = item.rawText || "";
  if (inputUrl) inputUrl.value = item.rawUrl || "";
  setActivePreset(0);
  updateCharCount();

  latestAnalysisData = item.analysisData;
  renderAnalysis(item.analysisData);
  navigateToPage("analisis");
  if (window.matchMedia("(max-width: 960px)").matches) {
    setTimeout(() => focusPanel("result-panel", true), 60);
  }
  showToast("Detail hasil pemindaian dibuka.", "info");
}

async function analyzeBatchContent() {
  const rawBatch = document.getElementById("batch-text").value.trim();
  if (!rawBatch) {
    showToast("Masukkan teks multi-narasi atau unggah berkas terlebih dahulu.", "info");
    return;
  }

  const splitter = /\r?\n\s*\r?\n/.test(rawBatch) ? /\r?\n\s*\r?\n/ : /\r?\n/;
  const items = rawBatch
    .split(splitter)
    .map(t => t.trim())
    .filter(t => t.length > 5);

  if (items.length === 0) {
    showToast("Tidak ditemukan narasi yang valid untuk diproses.", "info");
    return;
  }

  const btn = document.getElementById("btn-batch-analyze");
  btn.disabled = true;
  btn.textContent = `Memindai ${items.length} entri...`;

  const resultsContainer = document.getElementById("batch-results-container");
  const countBadge = document.getElementById("batch-count-badge");
  const tbody = document.getElementById("batch-tbody");

  resultsContainer.style.display = "block";
  countBadge.textContent = `Memproses 0 / ${items.length}...`;
  tbody.innerHTML = `<tr><td colspan="5" class="table-empty">Memproses pemindaian...</td></tr>`;

  const batchResults = [];
  latestBatchItems = [];
  const CHUNK_SIZE = 20;

  for (let offset = 0; offset < items.length; offset += CHUNK_SIZE) {
    const chunk = items.slice(offset, offset + CHUNK_SIZE);
    const payload = {
      items: chunk.map(entry => (/^https?:\/\/\S+$/i.test(entry) ? { text: null, url: entry } : { text: entry, url: null }))
    };

    try {
      const res = await fetch("/api/analyze/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Gagal memproses batch");
      }

      const json = await res.json();
      (json.results || []).forEach((resItem, localIdx) => {
        const rawEntry = chunk[localIdx] || "";
        const isUrl = /^https?:\/\/\S+$/i.test(rawEntry);
        const globalIdx = offset + localIdx + 1;

        if (resItem.status === "error" || !resItem.risk_assessment) {
          latestBatchItems.push(null);
          batchResults.push({
            idx: globalIdx,
            preview: rawEntry.length > 70 ? rawEntry.substring(0, 68) + "..." : rawEntry,
            score: 0,
            classification: "GAGAL ANALISIS",
            action: resItem.message || "ERROR",
            hasDetail: false
          });
        } else {
          const previewSrc = resItem.input_preview || rawEntry;
          latestBatchItems.push({
            rawText: isUrl ? "" : rawEntry,
            rawUrl: isUrl ? rawEntry : "",
            analysisData: resItem
          });
          batchResults.push({
            idx: globalIdx,
            preview: previewSrc.length > 70 ? previewSrc.substring(0, 68) + "..." : previewSrc,
            score: resItem.risk_assessment.score,
            classification: resItem.risk_assessment.classification,
            action: resItem.risk_assessment.action_code || "REVIEW",
            hasDetail: true
          });
        }
      });
    } catch (e) {
      chunk.forEach((rawEntry, localIdx) => {
        latestBatchItems.push(null);
        batchResults.push({
          idx: offset + localIdx + 1,
          preview: rawEntry.length > 50 ? rawEntry.substring(0, 48) + "..." : rawEntry,
          score: 0,
          classification: "ERROR KONEKSI",
          action: "ERROR",
          hasDetail: false
        });
      });
    }

    countBadge.textContent = `Memproses ${Math.min(offset + CHUNK_SIZE, items.length)} / ${items.length}...`;
  }

  countBadge.textContent = `${batchResults.length} selesai`;

  tbody.innerHTML = batchResults.map((item, rowIndex) => {
    let badgeClass = "badge-success";
    let scoreClass = "kb-score-low";
    if (item.score >= 70) {
      badgeClass = "badge-danger";
      scoreClass = "kb-score-high";
    } else if (item.score >= 45) {
      badgeClass = "badge-warning";
      scoreClass = "kb-score-mid";
    }

    const rowCls = item.hasDetail ? "batch-row-card batch-row-clickable" : "batch-row-card";
    const rowTitle = item.hasDetail ? 'title="Klik untuk membuka detail analisis"' : "";
    const detailHint = item.hasDetail ? `<span class="batch-row-hint">Ketuk untuk detail</span>` : "";

    return `
      <tr class="${rowCls}" data-batch-index="${rowIndex}" ${rowTitle}>
        <td class="td-no">#${item.idx}</td>
        <td class="td-snippet"><code>${escapeHtml(item.preview)}</code></td>
        <td class="td-score"><strong class="kb-score-val ${scoreClass}">${item.score}</strong> / 100</td>
        <td class="td-verdict"><span class="badge ${badgeClass}">${escapeHtml(item.classification)}</span></td>
        <td class="td-action">
          <span class="badge badge-dark">${escapeHtml(item.action)}</span>
          ${detailHint}
        </td>
      </tr>
    `;
  }).join("");

  btn.disabled = false;
  btn.textContent = "Jalankan Pemindaian";
  showToast(`Pemindaian selesai (${batchResults.length} entri).`, "success");
  if (window.matchMedia("(max-width: 768px)").matches) {
    resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-dot" aria-hidden="true"></span>
    <span>${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ============================================================================
// 8. INISIALISASI HALAMAN
// ============================================================================

function toggleSidebarMenu() {
  const sidebar = document.getElementById("app-sidebar");
  if (sidebar) sidebar.classList.toggle("collapsed");
}

function navigateToPage(pageName) {
  const targetName = pageName === "dashboard" ? "analisis" : pageName;
  const targetPage = document.getElementById(`page-${targetName}`);
  if (!targetPage) return;

  document.querySelectorAll(".app-page-view").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".sidebar-nav-btn").forEach(b => b.classList.remove("active"));

  targetPage.classList.add("active");
  const targetNav = document.getElementById(`nav-${targetName}`);
  if (targetNav) targetNav.classList.add("active");

  if (window.location.hash !== `#${targetName}`) {
    history.replaceState(null, null, `#${targetName}`);
  }
  window.scrollTo({ top: 0, behavior: "instant" });
}

function bindEvents() {
  const sidebarToggle = document.getElementById("btn-sidebar-toggle");
  if (sidebarToggle) sidebarToggle.addEventListener("click", toggleSidebarMenu);

  document.querySelectorAll(".sidebar-nav-btn[data-page]").forEach(btn => {
    btn.addEventListener("click", () => navigateToPage(btn.dataset.page));
  });

  document.querySelectorAll(".btn-sample[data-preset]").forEach(btn => {
    btn.addEventListener("click", () => loadPreset(Number(btn.dataset.preset)));
  });

  const bindClick = (id, fn) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", fn);
  };

  bindClick("btn-analyze", analyzeContent);
  bindClick("btn-clear-input", clearInputFields);
  bindClick("btn-scroll-input", () => {
    focusPanel("input-panel", false);
    const inputText = document.getElementById("input-text");
    if (inputText) inputText.focus({ preventScroll: true });
  });
  bindClick("btn-copy-report", copyTacticalReport);
  bindClick("btn-download-txt", () => downloadReport("txt"));
  bindClick("btn-download-json", () => downloadReport("json"));
  bindClick("btn-batch-analyze", analyzeBatchContent);
  bindClick("btn-clear-batch-file", clearBatchFile);
  bindClick("btn-toggle-add-kb", toggleAddFactCheckForm);
  bindClick("btn-cancel-add-kb", toggleAddFactCheckForm);
  bindClick("btn-clear-history", clearHistory);

  const inputText = document.getElementById("input-text");
  if (inputText) {
    inputText.addEventListener("input", () => {
      setActivePreset(0);
      updateCharCount();
    });
  }

  const inputUrl = document.getElementById("input-url");
  if (inputUrl) {
    inputUrl.addEventListener("input", () => setActivePreset(0));
  }

  const batchFile = document.getElementById("batch-file");
  if (batchFile) batchFile.addEventListener("change", handleBatchFileUpload);

  const dropzone = document.getElementById("batch-dropzone");
  if (dropzone) {
    dropzone.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
      const file = event.dataTransfer?.files?.[0];
      if (file) processBatchFile(file, batchFile);
    });
  }

  const batchTbody = document.getElementById("batch-tbody");
  if (batchTbody) {
    batchTbody.addEventListener("click", (event) => {
      const row = event.target.closest("tr.batch-row-clickable[data-batch-index]");
      if (!row) return;
      loadBatchItemDetail(Number(row.dataset.batchIndex));
    });
  }

  const kbForm = document.getElementById("kb-add-form");
  if (kbForm) kbForm.addEventListener("submit", submitNewFactCheck);

  const kbSearch = document.getElementById("kb-search");
  if (kbSearch) kbSearch.addEventListener("input", filterKnowledgeBase);

  const kbCat = document.getElementById("kb-filter-category");
  if (kbCat) kbCat.addEventListener("change", filterKnowledgeBase);

  const kbVerdict = document.getElementById("kb-filter-verdict");
  if (kbVerdict) kbVerdict.addEventListener("change", filterKnowledgeBase);

  const historyList = document.getElementById("history-list");
  if (historyList) {
    historyList.addEventListener("click", (event) => {
      const itemEl = event.target.closest(".history-item[data-history-index]");
      if (!itemEl) return;
      loadHistoryItem(Number(itemEl.dataset.historyIndex));
    });
  }

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "") || "analisis";
    navigateToPage(hash);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  updateCharCount();
  const initialHash = window.location.hash.replace("#", "") || "analisis";
  navigateToPage(initialHash);
  loadKnowledgeBase();
  renderHistory();
});
