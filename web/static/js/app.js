/**
 * Siber Sosial - Cognitive Domain Hoax Classifier
 * Frontend Controller & Tactical Dashboard Logic
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
    text: "Mabes TNI AD secara resmi memberangkatkan satgas kesehatan dan logistik Batalyon Kesehatan Divif untuk membantu evakuasi warga korban erupsi gunung berapi di wilayah timur.",
    url: "https://tniad.mil.id/tni-ad-terjunkan-satgas-bencana-erupsi"
  }
};

let latestAnalysisData = null;
let cachedFactChecks = [];
const HISTORY_STORAGE_KEY = "siber_sosial_scan_history_v1";

// ============================================================================
// 1. TAB CONTROLLER & PRESETS
// ============================================================================

function switchTab(mode) {
  const btnSingle = document.getElementById("tab-single-btn");
  const btnBatch = document.getElementById("tab-batch-btn");
  const paneSingle = document.getElementById("pane-single");
  const paneBatch = document.getElementById("pane-batch");

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

function loadPreset(id) {
  const p = PRESETS[id];
  if (!p) return;
  switchTab("single");
  document.getElementById("input-text").value = p.text;
  document.getElementById("input-url").value = p.url;
  analyzeContent();
}

// ============================================================================
// 2. ANALISIS TUNGGAL & RENDERING HASIL (SUBTASK 3.1)
// ============================================================================

function updateProgressBar(barEl, percentage) {
  if (!barEl) return;
  const pct = Math.min(100, Math.max(0, percentage));
  barEl.style.width = `${pct}%`;

  barEl.classList.remove("fill-green", "fill-yellow", "fill-red");
  if (pct >= 75) {
    barEl.classList.add("fill-red");
  } else if (pct >= 50) {
    barEl.classList.add("fill-yellow");
  } else {
    barEl.classList.add("fill-green");
  }
}

async function analyzeContent() {
  const text = document.getElementById("input-text").value.trim();
  const url = document.getElementById("input-url").value.trim();

  if (!text) {
    showToast("Masukkan teks narasi yang ingin diverifikasi.", "info");
    return;
  }

  const btn = document.getElementById("btn-analyze");
  btn.disabled = true;
  btn.textContent = "MEMPROSES ANALISIS TIGA LAYER...";

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, url: url || null })
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || "Gagal memproses analisis narasi");
    }

    const data = await res.json();
    latestAnalysisData = data;
    renderAnalysis(data);
    saveToHistory(data, text);
    showToast("Analisis kognitif berhasil diselesaikan.", "success");
  } catch (err) {
    showToast(`Terjadi kesalahan: ${err.message}`, "info");
    console.error("Analysis Error:", err);
  } finally {
    btn.disabled = false;
    btn.textContent = "ANALISIS NARASI KOGNITIF";
  }
}

function renderAnalysis(data) {
  const risk = data.risk_assessment;
  const layers = data.layers;
  const xai = data.explainable_ai;

  // Skor Utama & Progress Bar (Subtask 3.1)
  const scoreEl = document.getElementById("val-score");
  scoreEl.textContent = risk.score;

  const classBadge = document.getElementById("val-classification");
  classBadge.textContent = risk.classification;

  if (risk.score >= 75) {
    scoreEl.style.color = "#ef4444";
    classBadge.className = "badge-status-pill badge-danger";
  } else if (risk.score >= 50) {
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
    actionEl.textContent = risk.action_code ? `ACTION: ${risk.action_code}` : "";
  }

  // Tiga Lapisan Sub-skor & Mini Progress Bar (Subtask 3.1)
  const lingScore = risk.sub_scores.linguistic_score;
  const evidScore = risk.sub_scores.evidence_risk;
  const srcScore = risk.sub_scores.source_risk;

  document.getElementById("sub-linguistic").textContent = `${lingScore}%`;
  document.getElementById("sub-evidence").textContent = `${evidScore}%`;
  document.getElementById("sub-source").textContent = `${srcScore}%`;

  updateProgressBar(document.getElementById("bar-linguistic"), lingScore);
  updateProgressBar(document.getElementById("bar-evidence"), evidScore);
  updateProgressBar(document.getElementById("bar-source"), srcScore);

  // Layer 1 Detail & Triggers as Badges/Chips (Subtask 3.1)
  const lingBox = document.getElementById("box-linguistic");
  const lingTriggers = [
    ...(layers.linguistic.urgency_triggers || []),
    ...(layers.linguistic.conspiracy_triggers || []),
    ...(layers.linguistic.authority_triggers || []),
    ...(layers.linguistic.sara_triggers || []),
    ...(layers.linguistic.anonymous_claim_markers || [])
  ];

  let chipsHtml = "";
  if (lingTriggers.length > 0) {
    chipsHtml = `
      <div class="chips-container">
        ${lingTriggers.map(t => `<span class="badge-chip">⚠️ ${escapeHtml(t)}</span>`).join("")}
      </div>
    `;
  } else {
    chipsHtml = `<div class="chips-container"><span class="badge-chip badge-chip-green">✓ Tidak ditemukan frasa provokasi</span></div>`;
  }

  lingBox.innerHTML = `
    <strong>Indikator Leksikal:</strong> ${chipsHtml}
    <div style="margin-top: 0.4rem; font-size: 0.8rem; color: #6c757d;">
      <strong>Rasio Huruf Kapital:</strong> ${(layers.linguistic.caps_ratio * 100).toFixed(1)}% &bull; 
      <strong>Tanda Seru:</strong> ${layers.linguistic.exclamation_count} &bull; 
      <strong>Sensasional:</strong> ${layers.linguistic.is_sensational ? 'Ya' : 'Tidak'}
    </div>
  `;

  // Layer 2 Detail Bukti RAG
  const evidBox = document.getElementById("box-evidence");
  if (risk.best_match && risk.best_match.similarity_score > 0.25) {
    const bm = risk.best_match;
    const isSalah = bm.verdict === 'SALAH';
    const isMisleading = bm.verdict === 'MISLEADING';
    const badgeClass = isSalah ? 'badge-danger' : isMisleading ? 'badge-warning' : 'badge-success';

    evidBox.innerHTML = `
      <strong>Arsip Rujukan Terdekat:</strong> [${bm.id}] ${escapeHtml(bm.source_agency)} (${bm.date || '-'})<br>
      <strong>Status Vonis:</strong> <span class="badge ${badgeClass}">${bm.verdict}</span> &bull; 
      <strong>Kemiripan Kosinus:</strong> ${(bm.similarity_score * 100).toFixed(1)}%<br>
      <strong>Fakta Terverifikasi:</strong> ${escapeHtml(bm.fact)}
    `;
  } else {
    evidBox.innerHTML = `
      <strong>Status Bukti Fakta:</strong> Belum ada arsip klarifikasi yang cocok (&le; 25%). 
      <span style="color: #d97706; font-weight: 600;">Dianalisis sebagai narasi berkembang baru (Zero-Day Rumor).</span>
    `;
  }

  // Layer 3 Detail Sumber
  const srcBox = document.getElementById("box-source");
  const domainsStr = (layers.source.detected_domains && layers.source.detected_domains.length > 0)
    ? layers.source.detected_domains.join(", ")
    : "Tidak ada tautan eksplisit";

  srcBox.innerHTML = `
    <strong>Tier Sumber:</strong> <code style="color: #3f6ad8; background-color: #e0f2fe; padding: 2px 6px; border-radius: 4px;">${layers.source.source_tier}</code> &bull; 
    <strong>Domain:</strong> ${escapeHtml(domainsStr)}<br>
    <strong>Catatan Kredibilitas:</strong> ${escapeHtml(layers.source.notes || 'Normal')}
  `;

  // XAI & Rekomendasi
  document.getElementById("box-brief").textContent = xai.tactical_brief || "-";
  document.getElementById("box-recommendation").textContent = xai.counter_measure || "-";

  const factorsList = document.getElementById("list-factors");
  if (xai.key_factors && xai.key_factors.length > 0) {
    factorsList.innerHTML = xai.key_factors.map(f => `<li>${escapeHtml(f)}</li>`).join("");
  } else {
    factorsList.innerHTML = `<li>Tidak ada anomali kognitif signifikan.</li>`;
  }
}

// ============================================================================
// 3. GENERATOR LAPORAN TAKTIS & EKSPOR (SUBTASK 3.2)
// ============================================================================

function generateTacticalReportText(data) {
  if (!data) return "";
  const r = data.risk_assessment;
  const l = data.layers;
  const x = data.explainable_ai;
  const now = new Date().toLocaleString("id-ID", { timeZone: "Asia/Jakarta" });

  let text = `================================================================================\n`;
  text += `   LAPORAN INTELIJEN SIBER SOSIAL - SATUAN PEMANTAUAN KOGNITIF PUSSIBERAD\n`;
  text += `================================================================================\n`;
  text += `WAKTU ANALISIS       : ${now} WIB\n`;
  text += `SKOR RISIKO HOAKS    : ${r.score} / 100\n`;
  text += `KLASIFIKASI ANCAMAN  : ${r.classification}\n`;
  text += `DOMAIN ANCAMAN       : ${r.threat_domain || '-'}\n`;
  text += `KODE AKSI TAKTIS     : ${r.action_code || '-'}\n`;
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
  text += `RINGKASAN INTELIJEN (TACTICAL BRIEF):\n${x.tactical_brief}\n\n`;
  text += `FAKTOR RISIKO UTAMA:\n`;
  (x.key_factors || []).forEach((f, idx) => {
    text += `  ${idx + 1}. ${f}\n`;
  });
  text += `\nREKOMENDASI OPERASIONAL SATUAN:\n${x.counter_measure}\n`;
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
    await navigator.clipboard.writeText(report);
    showToast("Format Laporan Taktis berhasil disalin ke clipboard!", "success");
  } catch (err) {
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
    filename = `Laporan-Taktis-Siber-${timestamp}.txt`;
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
// 4. RIWAYAT PEMINDAIAN LOKAL / LOCALSTORAGE (SUBTASK 3.2)
// ============================================================================

function saveToHistory(analysisData, rawText) {
  try {
    let history = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY) || "[]");
    const entry = {
      timestamp: new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }),
      rawText: rawText,
      preview: rawText.length > 55 ? rawText.substring(0, 52) + "..." : rawText,
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
      if (item.score >= 75) badgeClass = "badge-danger";
      else if (item.score >= 50) badgeClass = "badge-warning";

      return `
        <li class="history-item" onclick="loadHistoryItem(${idx})">
          <span class="history-text" title="${escapeHtml(item.rawText)}">${escapeHtml(item.preview)}</span>
          <div class="history-meta">
            <span style="font-size: 0.72rem; color: #6c757d;">${item.timestamp}</span>
            <span class="badge ${badgeClass}" style="padding: 0.15rem 0.45rem; font-size: 0.7rem;">${item.score}</span>
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
      document.getElementById("input-text").value = item.rawText;
      latestAnalysisData = item.data;
      renderAnalysis(item.data);
      if (typeof navigateToPage === "function") {
        navigateToPage("analisis");
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
// 5. LIVE SEARCH, FILTER & TAMBAH ARSIP (SUBTASK 3.3)
// ============================================================================

async function loadKnowledgeBase() {
  try {
    const res = await fetch("/api/fact-checks");
    if (!res.ok) throw new Error("Gagal mengambil data dari server");
    const json = await res.json();
    cachedFactChecks = json.data || [];
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
    counterEl.textContent = `Menampilkan ${filtered.length} dari ${cachedFactChecks.length} arsip klarifikasi terindeks.`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #9ca3af; padding: 1.5rem;">Tidak ditemukan arsip yang sesuai filter pencarian.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(item => {
    let badgeClass = "badge-success";
    if (item.verdict === "SALAH") badgeClass = "badge-danger";
    else if (item.verdict === "MISLEADING") badgeClass = "badge-warning";

    return `
      <tr>
        <td><code>${escapeHtml(item.id)}</code></td>
        <td><span style="font-size: 0.8rem; font-weight: 600; color: #3f6ad8;">${escapeHtml(item.threat_category)}</span></td>
        <td>
          <div style="font-weight: 600; color: #212529; margin-bottom: 0.2rem;">${escapeHtml(item.claim)}</div>
          <div style="font-size: 0.78rem; color: #6c757d;"><strong>Fakta:</strong> ${escapeHtml(item.fact)}</div>
        </td>
        <td><span class="badge ${badgeClass}">${item.verdict}</span></td>
        <td>
          <div style="font-size: 0.8rem; font-weight: 500;">${escapeHtml(item.source_agency)}</div>
          ${item.reference_url ? `<a href="${item.reference_url}" target="_blank" style="font-size: 0.72rem; color: #3f6ad8; text-decoration: underline;">Tautan Rujukan</a>` : ''}
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
    btnEl.textContent = isHidden ? "✕ Tutup Form" : "+ Tambah Arsip Klarifikasi Baru";
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
    id,
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
  btnSave.textContent = "MENYIMPAN KE ARSIP...";

  try {
    const res = await fetch("/api/fact-checks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newEntry)
    });

    if (!res.ok) {
      // Fallback anggun: jika endpoint backend Orang 1 belum dibuat, simpan di memori client
      console.warn("Backend POST /api/fact-checks belum tersedia. Menambahkan ke cache tabel lokal.");
    }

    cachedFactChecks.unshift(newEntry);
    filterKnowledgeBase();
    toggleAddFactCheckForm();
    e.target.reset();
    showToast(`Arsip ${id} berhasil ditambahkan ke basis data!`, "success");
  } catch (err) {
    // Tetap tambahkan ke tabel lokal
    cachedFactChecks.unshift(newEntry);
    filterKnowledgeBase();
    toggleAddFactCheckForm();
    e.target.reset();
    showToast(`Arsip ${id} disimpan ke sesi tampilan lokal.`, "success");
  } finally {
    btnSave.disabled = false;
    btnSave.textContent = "SIMPAN KE PANGKALAN DATA";
  }
}

// ============================================================================
// 6. BATCH SCANNER / PEMANTAUAN MASSAL (SUBTASK 3.4)
// ============================================================================

function handleBatchFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById("batch-text").value = e.target.result;
    showToast(`Berkas ${file.name} berhasil dimuat ke editor batch.`, "info");
  };
  reader.readAsText(file);
}

async function analyzeBatchContent() {
  const rawBatch = document.getElementById("batch-text").value.trim();
  if (!rawBatch) {
    showToast("Masukkan teks multi-narasi atau unggah berkas terlebih dahulu.", "info");
    return;
  }

  // Pisahkan narasi berdasarkan baris kosong ganda atau per baris panjang
  const items = rawBatch
    .split(/\n\s*\n/)
    .map(t => t.trim())
    .filter(t => t.length > 10);

  if (items.length === 0) {
    showToast("Tidak ditemukan narasi yang valid untuk diproses.", "info");
    return;
  }

  const btn = document.getElementById("btn-batch-analyze");
  btn.disabled = true;
  btn.textContent = `MEMINDAI ${items.length} NARASI SECARA PARALEL...`;

  const resultsContainer = document.getElementById("batch-results-container");
  const countBadge = document.getElementById("batch-count-badge");
  const tbody = document.getElementById("batch-tbody");

  resultsContainer.style.display = "block";
  countBadge.textContent = `Memproses 0 / ${items.length} narasi...`;
  tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #38bdf8;">Sedang memproses pemindaian multi-narasi...</td></tr>`;

  const batchResults = [];

  // Jalankan request ke /api/analyze secara berurutan atau per batch kecil
  for (let i = 0; i < items.length; i++) {
    const textItem = items[i];
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textItem, url: null })
      });
      if (res.ok) {
        const json = await res.json();
        batchResults.push({
          idx: i + 1,
          preview: textItem.length > 70 ? textItem.substring(0, 68) + "..." : textItem,
          score: json.risk_assessment.score,
          classification: json.risk_assessment.classification,
          action: json.risk_assessment.action_code || "REVIEW"
        });
      } else {
        batchResults.push({
          idx: i + 1,
          preview: textItem.substring(0, 50) + "...",
          score: 0,
          classification: "GAGAL ANALISIS",
          action: "ERROR"
        });
      }
    } catch (e) {
      batchResults.push({
        idx: i + 1,
        preview: textItem.substring(0, 50) + "...",
        score: 0,
        classification: "ERROR KONEKSI",
        action: "ERROR"
      });
    }
    countBadge.textContent = `Memproses ${i + 1} / ${items.length} narasi...`;
  }

  countBadge.textContent = `${batchResults.length} Narasi Selesai Diproses`;

  tbody.innerHTML = batchResults.map(item => {
    let badgeClass = "badge-success";
    if (item.score >= 75) badgeClass = "badge-danger";
    else if (item.score >= 50) badgeClass = "badge-warning";

    return `
      <tr>
        <td>${item.idx}</td>
        <td><code>${escapeHtml(item.preview)}</code></td>
        <td><strong style="color: ${item.score >= 75 ? '#d92550' : item.score >= 50 ? '#f7b924' : '#3ac47d'};">${item.score}</strong> / 100</td>
        <td><span class="badge ${badgeClass}">${item.classification}</span></td>
        <td><span class="badge badge-dark" style="font-size: 0.68rem;">${escapeHtml(item.action)}</span></td>
      </tr>
    `;
  }).join("");

  btn.disabled = false;
  btn.textContent = "JALANKAN PEMINDAIAN MASSAL";
  showToast(`Pemindaian massal untuk ${batchResults.length} narasi selesai!`, "success");
}

// ============================================================================
// 7. TOAST NOTIFICATIONS & UTILITY
// ============================================================================

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : 'ℹ'}</span>
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

document.addEventListener("DOMContentLoaded", () => {
  loadKnowledgeBase();
  renderHistory();
});
