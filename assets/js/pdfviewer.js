export function initPdfViewer({
  canvasId,
  titleId,
  hintId,
  loadingId,
  prevId,
  nextId,
  zoomInId,
  zoomOutId,
}) {
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext("2d");

  const titleEl = document.getElementById(titleId);
  const hintEl = document.getElementById(hintId);
  const loadingEl = document.getElementById(loadingId);

  const prevBtn = document.getElementById(prevId);
  const nextBtn = document.getElementById(nextId);
  const zoomInBtn = document.getElementById(zoomInId);
  const zoomOutBtn = document.getElementById(zoomOutId);

  // PDF.js config
  // eslint-disable-next-line no-undef
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.js";

  let pdfDoc = null;
  let pageNum = 1;
  let scale = 1.2;

  async function renderPage(num) {
    if (!pdfDoc) return;

    loadingEl.classList.remove("hidden");

    const page = await pdfDoc.getPage(num);
    const viewport = page.getViewport({ scale });

    canvas.height = viewport.height;
    canvas.width = viewport.width;

    const renderTask = page.render({ canvasContext: ctx, viewport });
    await renderTask.promise;

    loadingEl.classList.add("hidden");
  }

  async function load(url, title = "Document") {
    try {
      titleEl.textContent = title;
      hintEl.textContent = url;

      loadingEl.classList.remove("hidden");
      // eslint-disable-next-line no-undef
      pdfDoc = await pdfjsLib.getDocument(url).promise;
      pageNum = 1;
      await renderPage(pageNum);
    } catch (e) {
      console.error(e);
      titleEl.textContent = "Failed to load PDF";
      hintEl.textContent = "Check file path and GitHub Pages permissions.";
      loadingEl.classList.add("hidden");
    }
  }

  prevBtn.onclick = async () => {
    if (!pdfDoc) return;
    pageNum = Math.max(1, pageNum - 1);
    await renderPage(pageNum);
  };

  nextBtn.onclick = async () => {
    if (!pdfDoc) return;
    pageNum = Math.min(pdfDoc.numPages, pageNum + 1);
    await renderPage(pageNum);
  };

  zoomInBtn.onclick = async () => {
    if (!pdfDoc) return;
    scale = Math.min(3.0, scale + 0.15);
    await renderPage(pageNum);
  };

  zoomOutBtn.onclick = async () => {
    if (!pdfDoc) return;
    scale = Math.max(0.6, scale - 0.15);
    await renderPage(pageNum);
  };

  return { load };
}
