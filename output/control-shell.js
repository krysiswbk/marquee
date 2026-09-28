/* Shared navigation and control behavior for Marquee's specialist settings workspaces. */
(() => {
  'use strict';
  document.body.classList.add('mq-controls');

  const path = location.pathname;
  const key = path === '/settings/layout'
    ? 'layout'
    : path === '/settings/attention'
      ? 'attention'
      : path === '/settings/tests'
        ? 'tests'
        : 'settings';
  const pages = [
    ['settings', 'Settings', '/settings'],
    ['layout', 'Layout', '/settings/layout?profile=cast'],
    ['attention', 'Alert rules', '/settings/attention'],
    ['tests', 'Test screens', '/settings/tests']
  ];

  const header = document.createElement('header');
  header.className = 'mq-shell';
  header.innerHTML = `<div class="mq-shell-inner">
    <a class="mq-brand" href="/settings" aria-label="Marquee settings"><span aria-hidden="true">M/</span><b>MARQUEE</b><small>CONTROL ROOM</small></a>
    <nav class="mq-primary" aria-label="Settings workspaces">${pages.map(([id, title, url]) => `<a href="${url}" ${id === key ? 'aria-current="page"' : ''}>${title}</a>`).join('')}</nav>
    <a class="mq-view" href="/live" target="_blank" rel="noopener">View display <span aria-hidden="true">↗</span></a>
  </div>`;

  document.body.prepend(header);
})();
