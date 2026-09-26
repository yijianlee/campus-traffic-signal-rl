/* Long details occupy a fixed dialog, with explicit page navigation. */
window.paginate = function(container, items, size, render) {
  let page = 0;
  const pages = Math.max(1, Math.ceil(items.length / size));
  const content = document.createElement('div'), footer = document.createElement('div');
  footer.className = 'pager';
  const previous = document.createElement('button'), label = document.createElement('span'), next = document.createElement('button');
  previous.textContent = '上一页'; next.textContent = '下一页';
  footer.append(previous, label, next); container.replaceChildren(content, footer);
  function draw() {
    render(content, items.slice(page * size, (page + 1) * size));
    label.textContent = `${page + 1} / ${pages}`;
    previous.disabled = page === 0; next.disabled = page === pages - 1;
  }
  previous.onclick = () => { page--; draw(); }; next.onclick = () => { page++; draw(); };
  draw();
};
