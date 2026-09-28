/* Shared navigation and control behavior for Marquee's specialist settings workspaces. */
(() => {
  'use strict';
  document.body.classList.add('mq-controls');

  const numericNames = {
    x: 'Horizontal position of this block', y: 'Vertical position of this block',
    width: 'Width of this block', scale: 'Size of this block',
    logoZoom: 'Logo zoom inside the Title block',
    customBackdropZoom: 'Custom backdrop zoom', customBackdropX: 'Custom backdrop horizontal focus',
    customBackdropY: 'Custom backdrop vertical focus', customBackdropOpacity: 'Custom backdrop opacity',
    customBackdropBlur: 'Custom backdrop blur', customBackdropBrightness: 'Custom backdrop brightness'
  };
  const humanize = value => value.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[-_.]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const numericName = control => {
    const key = control.dataset.layoutField || control.dataset.backdropField || control.dataset.field;
    return numericNames[key] || (key ? humanize(key) : control.id ? humanize(control.id) : '');
  };
  const numericId = (control, index) => {
    if (control.id) return control.id;
    const key = control.dataset.layoutField || control.dataset.backdropField || control.dataset.field || `control-${index}`;
    const base = `numeric-${key.replace(/[^a-zA-Z0-9_-]+/g, '-')}`;
    return document.getElementById(base) ? `${base}-${index}` : base;
  };
  function enhanceNumericControls(root = document) {
    root.querySelectorAll('input[type="number"], input[type="range"]').forEach((control, index) => {
      control.id = numericId(control, index);
      const label = root.querySelector(`label[for="${CSS.escape(control.id)}"]`) || control.closest('label');
      if (!label && !control.getAttribute('aria-label')) {
        const name = numericName(control);
        if (name) control.setAttribute('aria-label', name);
      }
      const describedBy = (control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
      if (!describedBy.some(id => document.getElementById(id))) {
        const help = document.createElement('small');
        help.id = `${control.id}-help`; help.className = 'numeric-help';
        help.textContent = `Allowed range: ${control.min}–${control.max}; step ${control.step || 'any'}.`;
        control.insertAdjacentElement('afterend', help);
        describedBy.push(help.id); control.setAttribute('aria-describedby', describedBy.join(' '));
      }
    });
  }
  window.MarqueeNumericControls = { enhance: enhanceNumericControls };
  enhanceNumericControls();

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
