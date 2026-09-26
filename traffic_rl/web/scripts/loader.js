/* Script chunks work over HTTP and file://. Keep at most two decoded runs. */
window.TRAFFIC_CHUNKS = Object.create(null);
window.ReplayLoader = (() => {
  const recent = [], pending = new Map();
  async function load(entry) {
    if (entry.frames) return entry; // Historical packages remain readable.
    const key = entry.key;
    let run = window.TRAFFIC_CHUNKS[key];
    if (!run) {
      if (!pending.has(key)) pending.set(key, new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = entry.src;
        const finish = () => { script.remove(); pending.delete(key); };
        script.onload = () => {
          const run = window.TRAFFIC_CHUNKS[key]; finish();
          run?.frames?.length ? resolve(run) : reject(new Error('记录内容不完整'));
        };
        script.onerror = () => { finish(); reject(new Error('无法读取记录，请保留完整导出文件夹')); };
        document.head.append(script);
      }));
      run = await pending.get(key);
    }
    const old = recent.indexOf(key); if (old >= 0) recent.splice(old, 1);
    recent.push(key);
    while (recent.length > 2) delete window.TRAFFIC_CHUNKS[recent.shift()];
    return run;
  }
  return { load };
})();
