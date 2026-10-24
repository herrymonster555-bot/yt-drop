const input = document.getElementById("pinUrl");
const pasteBtn = document.getElementById("pasteBtn");
const downloadBtn = document.getElementById("downloadBtn");
const actualDownloadBtn = document.getElementById("actualDownloadBtn");
const statusBox = document.getElementById("status");
const resultCard = document.getElementById("result");
const previewImage = document.getElementById("previewImage");
const resultTitle = document.getElementById("resultTitle");
const resultMeta = document.getElementById("resultMeta");
const qualityPanel = document.getElementById("qualityPanel");
const videoQuality = document.getElementById("videoQuality");
const videoQualityHelp = document.getElementById("videoQualityHelp");
const audioQualityGroup = document.getElementById("audioQualityGroup");
const audioBitrate = document.getElementById("audioBitrate");
let currentUrl = "";
let currentInfo = null;
let busy = false;
document.getElementById("year").textContent = new Date().getFullYear();
function selectedFormat() { return document.querySelector('input[name="format"]:checked')?.value || "mp4"; }
function qualityLabel(height) {
  if (height >= 4320) return `${height}p · 8K`;
  if (height >= 2160) return `${height}p · 4K UHD`;
  if (height >= 1440) return `${height}p · 2K / QHD`;
  return `${height}p`;
}
function renderQualityOptions() {
  const format = selectedFormat();
  qualityPanel.hidden = !currentInfo;
  audioQualityGroup.hidden = format !== "mp3";
  videoQuality.hidden = format !== "mp4";
  videoQualityHelp.hidden = format !== "mp4";
  document.querySelectorAll(".quality-panel > .quality-label").forEach(label => { label.hidden = label.htmlFor !== "videoQuality" && format !== "mp4"; });
  if (format === "mp4" && currentInfo) {
    const heights = [...new Set((currentInfo.available_heights || []).map(Number))].filter(h => Number.isFinite(h) && h > 0).sort((a,b) => b-a);
    const previous = videoQuality.value;
    videoQuality.replaceChildren();
    const best = document.createElement("option"); best.value = "best"; best.textContent = "Best available (original quality)"; videoQuality.append(best);
    heights.forEach(height => { const option = document.createElement("option"); option.value = String(height); option.textContent = qualityLabel(height); videoQuality.append(option); });
    if ([...videoQuality.options].some(o => o.value === previous)) videoQuality.value = previous;
    videoQualityHelp.textContent = heights.length ? `Detected resolutions: ${heights.slice().sort((a,b)=>a-b).map(h => qualityLabel(h)).join(", ")}. Only available qualities are listed.` : "No separate resolution list was returned; Best available will select the best compatible format.";
  }
  if (currentInfo) resultMeta.textContent = format === "mp3"
    ? `Audio extraction · ${audioBitrate.value} kbps MP3 selected`
    : `${currentInfo.duration ? `${Math.round(currentInfo.duration)} seconds` : "Video details found"} · ${videoQuality.value === "best" ? "Best available" : qualityLabel(Number(videoQuality.value))} selected`;
}
document.querySelectorAll('input[name="format"]').forEach(radio => radio.addEventListener("change", () => {
  document.querySelectorAll(".format-option").forEach(label => label.classList.toggle("selected", label.querySelector("input").checked));
  renderQualityOptions();
}));
videoQuality.addEventListener("change", renderQualityOptions);
audioBitrate.addEventListener("change", renderQualityOptions);
function setStatus(message, type = "loading") { statusBox.textContent = message; statusBox.className = `status ${type}`; statusBox.hidden = !message; }
function setBusy(value) { busy = value; downloadBtn.disabled = value; downloadBtn.innerHTML = value ? '<span class="spinner"></span> Checking…' : '<span class="download-symbol">↓</span> Find video'; }
function cleanResult() { resultCard.hidden = true; previewImage.hidden = true; previewImage.removeAttribute("src"); qualityPanel.hidden = true; currentInfo = null; }
async function parseResponse(response) { const contentType = response.headers.get("content-type") || ""; if (contentType.includes("application/json")) return await response.json(); return { ok: false, error: "Unexpected server response. Check that the backend is running." }; }
async function resolveVideo() {
  if (busy) return;
  const url = input.value.trim();
  if (!url) { cleanResult(); setStatus("Paste a YouTube video link to get started.", "error"); input.focus(); return; }
  currentUrl = url; cleanResult(); setBusy(true); setStatus("Checking the video and detecting its available resolutions…", "loading");
  try {
    const response = await fetch("/api/resolve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
    const data = await parseResponse(response);
    if (!response.ok || !data.ok) throw new Error(data.error || "Could not find this video.");
    currentInfo = data;
    resultTitle.textContent = data.title || "YouTube video";
    if (data.thumbnail) { previewImage.src = data.thumbnail; previewImage.hidden = false; previewImage.onerror = () => { previewImage.hidden = true; }; }
    resultCard.hidden = false; renderQualityOptions();
    setStatus("Video found. Choose an available resolution or MP3 bitrate, then download.", "success");
  } catch (error) { setStatus(error.message || "Something went wrong. Try another public YouTube video.", "error"); }
  finally { setBusy(false); }
}
downloadBtn.addEventListener("click", resolveVideo);
input.addEventListener("keydown", event => { if (event.key === "Enter") resolveVideo(); });
pasteBtn.addEventListener("click", async () => { try { if (!navigator.clipboard?.readText) throw new Error(); input.value = await navigator.clipboard.readText(); input.focus(); setStatus("Link pasted. Click Find video to continue.", "success"); } catch { input.focus(); setStatus("Clipboard access was blocked. Paste the link using Ctrl+V.", "error"); } });
const progressPanel = document.getElementById("progressPanel");
const progressPercent = document.getElementById("progressPercent");
const progressBarPercent = document.getElementById("progressBarPercent");
const progressBarFill = document.getElementById("progressBarFill");
const progressRing = document.getElementById("progressRing");
const progressTitle = document.getElementById("progressTitle");
const progressStage = document.getElementById("progressStage");
const progressDetails = document.getElementById("progressDetails");
const progressSuccess = document.getElementById("progressSuccess");
let activeDownload = false;
function updateProgressUI(job) {
  const percent = Math.max(0, Math.min(100, Number(job.percent) || 0));
  const shown = `${Math.round(percent)}%`;
  progressPercent.textContent = shown;
  progressBarPercent.textContent = shown;
  progressBarFill.style.width = `${percent}%`;
  const circumference = 2 * Math.PI * 49;
  progressRing.style.strokeDasharray = String(circumference);
  progressRing.style.strokeDashoffset = String(circumference * (1 - percent / 100));
  progressStage.textContent = job.stage || "Preparing your download…";
  if (job.state === "queued") progressTitle.textContent = "Getting things ready";
  else if (job.state === "processing") progressTitle.textContent = "Finishing your media";
  else if (job.state === "complete") progressTitle.textContent = "Your file is ready";
  else progressTitle.textContent = "Preparing your download";
  const details = [];
  if (job.speed) details.push(job.speed);
  if (job.eta) details.push(`ETA ${job.eta}`);
  progressDetails.textContent = details.length ? details.join(" · ") : (job.state === "complete" ? "Your file is ready to save." : "Progress is reported by the download engine. Keep this tab open.");
  progressSuccess.hidden = job.state !== "complete";
}
async function waitForJob(jobId) {
  while (activeDownload) {
    const response = await fetch(`/api/progress/${encodeURIComponent(jobId)}`, { cache: "no-store" });
    const job = await parseResponse(response);
    if (!response.ok || !job.ok) throw new Error(job.error || "Could not read download progress.");
    updateProgressUI(job);
    if (job.state === "error") throw new Error(job.error || "Download failed.");
    if (job.state === "complete") return;
    await new Promise(resolve => setTimeout(resolve, 450));
  }
  throw new Error("Download cancelled.");
}
actualDownloadBtn.addEventListener("click", async () => {
  if (!currentUrl || busy || activeDownload) return;
  const format = selectedFormat();
  const payload = { url: currentUrl, format };
  if (format === "mp3") payload.bitrate = audioBitrate.value;
  else payload.quality = videoQuality.value;
  activeDownload = true;
  actualDownloadBtn.disabled = true;
  actualDownloadBtn.textContent = "Processing…";
  progressPanel.hidden = false;
  progressSuccess.hidden = true;
  updateProgressUI({ percent: 1, state: "queued", stage: format === "mp3" ? `Preparing ${audioBitrate.value} kbps MP3 audio` : `Preparing ${videoQuality.value === "best" ? "best available quality" : qualityLabel(Number(videoQuality.value))}` });
  setStatus("Your download is processing. You can follow its live progress below.", "loading");
  try {
    const response = await fetch("/api/download", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await parseResponse(response);
    if (!response.ok || !data.ok || !data.job_id) throw new Error(data.error || "Could not start the download.");
    await waitForJob(data.job_id);
    progressTitle.textContent = "Download ready!";
    progressStage.textContent = "Sending your file to the browser…";
    progressDetails.textContent = "Almost there — your browser will save the file.";
    const fileResponse = await fetch(`/api/file/${encodeURIComponent(data.job_id)}`);
    const contentType = fileResponse.headers.get("content-type") || "";
    if (!fileResponse.ok || contentType.includes("application/json")) {
      const errorData = contentType.includes("application/json") ? await fileResponse.json() : null;
      throw new Error(errorData?.error || "The prepared file could not be downloaded.");
    }
    const blob = await fileResponse.blob();
    const disposition = fileResponse.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const filename = match ? match[1] : `yt-drop.${format}`;
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = objectUrl; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(objectUrl), 15000);
    updateProgressUI({ percent: 100, state: "complete", stage: "Download complete" });
    progressTitle.textContent = "You're all set!";
    progressStage.textContent = "Your file has been sent to the browser.";
    progressDetails.textContent = "Check your browser's downloads.";
    setStatus("Download complete. Please respect the creator’s rights.", "success");
  } catch (error) {
    progressTitle.textContent = "We hit a snag";
    progressStage.textContent = error.message || "Download failed. Please try again.";
    progressDetails.textContent = "Check the link and try again. For MP3 or merged MP4, FFmpeg must be installed on the server.";
    setStatus(error.message || "Download failed. Please try another video.", "error");
  } finally {
    activeDownload = false;
    actualDownloadBtn.disabled = false;
    actualDownloadBtn.innerHTML = 'Download file <span>↓</span>';
  }
});

const menuToggle = document.getElementById("menuToggle");
menuToggle.addEventListener("click", () => { const nav = document.querySelector(".desktop-nav"); const open = nav.classList.toggle("open"); menuToggle.setAttribute("aria-expanded", String(open)); });
document.querySelectorAll(".desktop-nav a").forEach(a => a.addEventListener("click", () => { document.querySelector(".desktop-nav").classList.remove("open"); menuToggle.setAttribute("aria-expanded", "false"); }));
if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add("is-visible"); observer.unobserve(entry.target); } }), { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach(el => observer.observe(el));
} else document.querySelectorAll(".reveal").forEach(el => el.classList.add("is-visible"));
