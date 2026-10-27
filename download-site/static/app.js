(() => {
  const bar = document.getElementById('progress');
  const percent = document.getElementById('percent');
  const speed = document.getElementById('speed');
  if (!bar || !percent || !speed) return;
  let value = 72;
  setInterval(() => {
    value += Math.floor(Math.random() * 4) + 1;
    if (value >= 99) value = 62;
    bar.style.width = value + '%';
    percent.textContent = value + '%';
    speed.textContent = (5.2 + Math.random() * 5.6).toFixed(1) + ' MB/s';
  }, 1400);
})();