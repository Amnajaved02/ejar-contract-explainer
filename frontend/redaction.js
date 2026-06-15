/*
 * Client-side, model-free PII redaction for Ejar PDFs (v2).
 * Runs entirely in the browser via pdf.js — personal data never leaves the device.
 *
 * Approach: find always-present English field labels (even multi-word ones), then
 * paint ONE opaque band from each PII label to the next field label. This covers the
 * value regardless of script (Arabic names included) or how pdf.js tokenizes it.
 *
 * Exposes: window.EjarRedactor.redact(file) -> { images, stats }
 *   stats = { pages, matchedLabels: string[], boxesDrawn }
 * Throws RedactionError('no_text_layer' | 'no_labels').
 */
(function () {
  const PII_LABELS = [
    "Name", "ID No.", "Mobile No.", "Email", "National Address", "CR No.",
    "Broker Name", "Title Deed No.", "Main Contract No.", "Contract No.",
    "Landline No.", "Fax No.", "Electricity meter number",
    "Gas meter number", "Water meter number",
  ];
  // Every English field label = a boundary that stops a redaction band.
  const STOP_LABELS = PII_LABELS.concat([
    "Contract Type", "Contract Sealing Location", "Contract Sealing Date",
    "Tenancy Start Date", "Tenancy End Date", "Nationality", "ID Type",
    "Issuer", "Place of Issue", "Issue Date", "Title deed type",
    "Property Type", "Property Usage", "Number of Units", "Number of Floors",
    "Number of Parking Lots", "Number of Elevators", "Unit No.", "Unit Type",
    "Unit Area", "Floor No.", "Furnished", "Furnishing Status",
    "Number of AC units", "Kitchen Cabinets Installed", "Annual Rent",
    "Regular Rent Payment", "Last Rent Payment", "Rent payment cycle",
    "Security Deposit", "Brokerage Entity Name", "Brokerage Entity Address",
  ]);

  class RedactionError extends Error { constructor(code){ super(code); this.code = code; } }
  const norm = (s) => s.replace(/[:：.]/g, " ").replace(/\s+/g, " ").trim().toLowerCase();

  // Find labels (possibly split across items) in a row sorted by x.
  function findLabels(items, labels) {
    const out = [];
    for (const lab of labels) {
      const nlab = norm(lab);
      for (let i = 0; i < items.length; i++) {
        let run = "", j = i;
        while (j < items.length && norm(run).length < nlab.length) {
          run = (run + " " + items[j].str).trim(); j++;
        }
        if (norm(run) === nlab || norm(run).startsWith(nlab + " ") || norm(run) === nlab) {
          out.push({ label: lab, rightX: items[j - 1].x + items[j - 1].w, leftX: items[i].x });
          break;
        }
      }
    }
    return out;
  }

  async function redact(file) {
    const pdfjsLib = window.pdfjsLib;
    const pdf = await pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
    const images = [];
    let totalText = 0;
    const matched = new Set();
    let boxesDrawn = 0;
    const debug = /[?&]debug=1/.test(location.search);

    for (let n = 1; n <= pdf.numPages; n++) {
      const page = await pdf.getPage(n);
      const scale = 2.0;
      const viewport = page.getViewport({ scale });
      const content = await page.getTextContent();

      const items = content.items.map((it) => {
        const tm = pdfjsLib.Util.transform(viewport.transform, it.transform);
        const fontH = Math.hypot(tm[2], tm[3]) || 10;
        return { str: it.str, x: tm[4], y: tm[5] - fontH, w: (it.width || 0) * scale, h: fontH };
      }).filter((i) => i.str && i.str.trim());
      totalText += items.reduce((a, i) => a + i.str.trim().length, 0);

      // group into rows by vertical proximity
      items.sort((a, b) => a.y - b.y || a.x - b.x);
      const rows = [];
      for (const it of items) {
        let row = rows.find((r) => Math.abs(r.y - it.y) <= it.h * 0.7);
        if (!row) { row = { y: it.y, top: it.y, bot: it.y + it.h, items: [] }; rows.push(row); }
        row.items.push(it);
        row.top = Math.min(row.top, it.y); row.bot = Math.max(row.bot, it.y + it.h);
      }

      // render the page
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width; canvas.height = viewport.height;
      const ctx = canvas.getContext("2d");
      await page.render({ canvasContext: ctx, viewport }).promise;

      // estimate vertical row spacing (cell height) on this page
      const ys = rows.map((r) => r.y).sort((a, b) => a - b);
      const gaps = [];
      for (let k = 1; k < ys.length; k++) { const g = ys[k] - ys[k - 1]; if (g > 3) gaps.push(g); }
      gaps.sort((a, b) => a - b);
      const pitch = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 26;

      // paint a FULL-CELL band per PII label: values in this layout sit ABOVE the
      // label (and can wrap below), so extend up ~1 pitch and down ~0.7 pitch.
      for (const row of rows) {
        const its = row.items.slice().sort((a, b) => a.x - b.x);
        const piiHits = findLabels(its, PII_LABELS);
        const stopHits = findLabels(its, STOP_LABELS);
        for (const hit of piiHits) {
          matched.add(hit.label);
          let stopX = canvas.width;
          for (const s of stopHits) if (s.leftX > hit.rightX + 1) stopX = Math.min(stopX, s.leftX);
          const x = hit.rightX + 1;
          const w = Math.max(0, stopX - x - 1);
          if (w > 4) {
            const yTop = row.top - pitch * 1.1;
            const yBot = row.bot + pitch * 0.7;
            ctx.fillStyle = "#111";
            ctx.fillRect(x, yTop, w, yBot - yTop);
            boxesDrawn++;
            if (debug) { ctx.strokeStyle = "#e00"; ctx.lineWidth = 1; ctx.strokeRect(hit.leftX, row.top - 2, hit.rightX - hit.leftX, (row.bot - row.top) + 4); }
          }
        }
      }
      images.push(await new Promise((res) => canvas.toBlob(res, "image/png")));
    }

    if (totalText < 30) throw new RedactionError("no_text_layer");
    if (matched.size === 0) throw new RedactionError("no_labels");
    return { images, stats: { pages: pdf.numPages, matchedLabels: [...matched], boxesDrawn } };
  }

  window.EjarRedactor = { redact, RedactionError, PII_LABELS };
})();
