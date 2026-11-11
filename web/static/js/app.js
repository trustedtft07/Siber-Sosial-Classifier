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

function loadPreset(id) {
  const p = PRESETS[id];
  if (!p) return;
  document.getElementById("input-text").value = p.text;
  document.getElementById("input-url").value = p.url;
  analyzeContent();
}

async function analyzeContent() {
  const text = document.getElementById("input-text").value.trim();
  const url = document.getElementById("input-url").value.trim();

  if (!text) {
    alert("Masukkan teks narasi yang ingin diverifikasi.");
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

    if (!res.ok) throw new Error("Gagal melakukan analisis");
    const data = await res.json();
    renderAnalysis(data);
  } catch (err) {
    alert("Terjadi kesalahan teknis: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "ANALISIS NARASI KOGNITIF";
  }
}

function renderAnalysis(data) {
  const risk = data.risk_assessment;
  const layers = data.layers;
  const xai = data.explainable_ai;

  const scoreEl = document.getElementById("val-score");
  scoreEl.textContent = risk.score;

  const classBadge = document.getElementById("val-classification");
  classBadge.textContent = risk.classification;

  if (risk.score >= 75) {
    scoreEl.style.color = "#ef4444";
    classBadge.className = "badge badge-red";
  } else if (risk.score >= 50) {
    scoreEl.style.color = "#f59e0b";
    classBadge.className = "badge badge-yellow";
  } else {
    scoreEl.style.color = "#10b981";
    classBadge.className = "badge badge-green";
  }

  document.getElementById("val-domain").textContent = risk.threat_domain;
  document.getElementById("sub-linguistic").textContent = risk.sub_scores.linguistic_score + "%";
  document.getElementById("sub-evidence").textContent = risk.sub_scores.evidence_risk + "%";
  document.getElementById("sub-source").textContent = risk.sub_scores.source_risk + "%";

  const lingBox = document.getElementById("box-linguistic");
  const lingTriggers = [
    ...layers.linguistic.urgency_triggers,
    ...layers.linguistic.conspiracy_triggers,
    ...layers.linguistic.authority_triggers,
    ...layers.linguistic.sara_triggers
  ];
  lingBox.innerHTML = `
    <strong>Indikator Leksikal:</strong> ${lingTriggers.length > 0 ? lingTriggers.join(", ") : "Tidak terdeteksi frasa provokasi"}<br>
    <strong>Rasio Huruf Kapital:</strong> ${(layers.linguistic.caps_ratio * 100).toFixed(1)}% | <strong>Tanda Seru:</strong> ${layers.linguistic.exclamation_count}
  `;

  const evidBox = document.getElementById("box-evidence");
  if (risk.best_match) {
    const bm = risk.best_match;
    evidBox.innerHTML = `
      <strong>Arsip Rujukan:</strong> [${bm.id}] ${bm.source_agency} (${bm.date})<br>
      <strong>Status Klarifikasi:</strong> <span class="badge ${bm.verdict === 'SALAH' ? 'badge-red' : 'badge-green'}">${bm.verdict}</span> (Kemiripan: ${(bm.similarity_score * 100).toFixed(1)}%)<br>
      <strong>Fakta Terverifikasi:</strong> ${bm.fact}
    `;
  } else {
    evidBox.innerHTML = `<strong>Status Bukti:</strong> Belum ada arsip klarifikasi yang cocok (>25%). Dianalisis sebagai isu berkembang baru.`;
  }

  const srcBox = document.getElementById("box-source");
  srcBox.innerHTML = `
    <strong>Tier Sumber:</strong> ${layers.source.source_tier}<br>
    <strong>Domain:</strong> ${layers.source.detected_domains.length > 0 ? layers.source.detected_domains.join(", ") : "Tidak ada URL primer"}<br>
    <strong>Catatan:</strong> ${layers.source.notes}
  `;

  document.getElementById("box-brief").textContent = xai.tactical_brief;
  document.getElementById("box-recommendation").textContent = xai.counter_measure;

  const factorsList = document.getElementById("list-factors");
  factorsList.innerHTML = xai.key_factors.map(f => `<li>${f}</li>`).join("");
}

async function loadKnowledgeBase() {
  try {
    const res = await fetch("/api/fact-checks");
    const json = await res.json();
    const tbody = document.getElementById("kb-tbody");
    tbody.innerHTML = json.data.map(item => `
      <tr>
        <td><code>${item.id}</code></td>
        <td>${item.threat_category}</td>
        <td>${item.claim}</td>
        <td><span class="badge ${item.verdict === 'SALAH' ? 'badge-red' : item.verdict === 'MISLEADING' ? 'badge-yellow' : 'badge-green'}">${item.verdict}</span></td>
        <td>${item.source_agency}</td>
      </tr>
    `).join("");
  } catch (e) {
    console.error("Gagal memuat arsip:", e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadKnowledgeBase();
});
