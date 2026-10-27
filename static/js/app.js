/* EpicOutlet storefront behaviour: toasts, cart, wishlist, live search. */
(function () {
  'use strict';
  const EO = window.EO || {};

  // Toasts ------------------------------------------------------------------
  const ICONS = { success: 'fa-circle-check', error: 'fa-circle-exclamation', info: 'fa-circle-info' };
  EO.toast = function (text, level, link) {
    level = level === 'danger' || level === 'warning' ? 'error' : (ICONS[level] ? level : 'info');
    const stack = document.getElementById('toastStack');
    if (!stack) return;
    const el = document.createElement('div');
    el.className = 'eo-toast ' + level;
    const icon = document.createElement('i');
    icon.className = 'fa-solid ' + ICONS[level];
    icon.setAttribute('aria-hidden', 'true');
    const span = document.createElement('span');
    span.textContent = text;
    el.append(icon, span);
    if (link) {
      const a = document.createElement('a');
      a.href = link.href;
      a.textContent = link.label;
      el.append(a);
    }
    stack.append(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, 3800);
    setTimeout(() => el.remove(), 4200);
  };

  // Fetch helper --------------------------------------------------------------
  EO.post = async function (url, data, isForm) {
    const headers = { 'X-CSRFToken': EO.csrf, 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' };
    let body = data;
    if (!isForm) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(data || {});
    }
    const res = await fetch(url, { method: 'POST', credentials: 'same-origin', headers, body });
    let json = {};
    try { json = await res.json(); } catch (e) { /* non-JSON error page */ }
    if (res.status === 401) {
      window.location.href = EO.loginUrl + '?next=' + encodeURIComponent(window.location.pathname + window.location.search);
      throw new Error('login required');
    }
    if (!res.ok) {
      const err = new Error(json.status || 'Something went wrong. Please try again.');
      err.data = json;
      err.statusCode = res.status;
      throw err;
    }
    return json;
  };

  function setBadge(selector, count) {
    document.querySelectorAll(selector).forEach((el) => {
      el.dataset.count = count;
      el.textContent = count > 0 ? count : '';
    });
  }
  EO.setCartCount = (n) => setBadge('[data-cart-count]', n);
  EO.formatINR = (n) => '₹' + Number(n || 0).toLocaleString('en-IN');

  // Wishlist toggle ---------------------------------------------------------
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-wishlist]');
    if (!btn) return;
    e.preventDefault();
    if (!EO.isAuth) { window.location.href = EO.loginUrl + '?next=' + encodeURIComponent(location.pathname); return; }
    btn.disabled = true;
    try {
      const data = await EO.post(EO.urls.wishlist, { pid: btn.dataset.wishlist });
      document.querySelectorAll('[data-wishlist="' + btn.dataset.wishlist + '"]').forEach((b) => {
        b.classList.toggle('active', data.in_wishlist);
        b.setAttribute('aria-pressed', data.in_wishlist ? 'true' : 'false');
        const label = b.querySelector('[data-wishlist-label]');
        if (label) label.textContent = data.in_wishlist ? 'Saved' : 'Save';
      });
      setBadge('[data-wishlist-count]', data.wishlist_count);
      EO.toast(data.status, 'success');
    } catch (err) {
      if (err.message !== 'login required') EO.toast(err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  // Add to cart (product page) ---------------------------------------------
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-add-to-cart]');
    if (!btn) return;
    e.preventDefault();
    const qtyInput = document.querySelector(btn.dataset.qtyInput || '#txtQty');
    const qty = parseInt(qtyInput ? qtyInput.value : '1', 10) || 1;
    btn.disabled = true;
    try {
      const data = await EO.post(EO.urls.addToCart, { pid: btn.dataset.addToCart, product_qty: qty });
      EO.setCartCount(data.cart_count);
      EO.toast(data.status, 'success', { href: EO.urls.cart, label: 'View cart' });
      if (btn.dataset.buyNow !== undefined) window.location.href = btn.dataset.buyNow;
    } catch (err) {
      if (err.message !== 'login required') EO.toast(err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  // Quantity steppers ---------------------------------------------------------
  document.addEventListener('click', (e) => {
    const step = e.target.closest('[data-step]');
    if (!step) return;
    const wrap = step.closest('.qty-stepper');
    const input = wrap.querySelector('input');
    const max = parseInt(input.max || '10', 10);
    const next = Math.min(max, Math.max(1, (parseInt(input.value, 10) || 1) + parseInt(step.dataset.step, 10)));
    if (next !== parseInt(input.value, 10)) {
      input.value = next;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
    wrap.querySelector('[data-step="-1"]').disabled = next <= 1;
    wrap.querySelector('[data-step="1"]').disabled = next >= max;
  });

  // Cart page: live quantity updates -----------------------------------------
  function renderSummary(data) {
    const set = (sel, val) => document.querySelectorAll(sel).forEach((el) => { el.textContent = val; });
    set('[data-summary="subtotal"]', EO.formatINR(data.subtotal));
    set('[data-summary="shipping"]', data.shipping ? EO.formatINR(data.shipping) : 'Free');
    set('[data-summary="total"]', EO.formatINR(data.total));
    set('[data-summary="savings"]', EO.formatINR(data.savings));
    const gap = document.querySelector('[data-free-ship]');
    if (gap) gap.hidden = !data.free_shipping_gap;
    set('[data-summary="gap"]', EO.formatINR(data.free_shipping_gap));
    EO.setCartCount(data.cart_count);
    if (data.wishlist_count !== undefined) setBadge('[data-wishlist-count]', data.wishlist_count);
    if (!data.cart_count) window.location.reload();
  }

  let qtyTimer;
  document.addEventListener('change', (e) => {
    const input = e.target.closest('[data-cart-qty]');
    if (!input) return;
    clearTimeout(qtyTimer);
    qtyTimer = setTimeout(async () => {
      try {
        const data = await EO.post(EO.urls.updateCart, { cid: input.dataset.cartQty, product_qty: input.value });
        const line = document.querySelector('[data-line-total="' + input.dataset.cartQty + '"]');
        if (line) line.textContent = EO.formatINR(data.line_total);
        renderSummary(data);
      } catch (err) {
        if (err.data && err.data.product_qty) input.value = err.data.product_qty;
        EO.toast(err.message, 'error');
      }
    }, 350);
  });

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-cart-remove]');
    if (!btn) return;
    e.preventDefault();
    btn.disabled = true;
    try {
      const data = await EO.post(btn.dataset.cartRemove, {});
      const row = btn.closest('.line-item');
      if (row) row.remove();
      EO.toast(data.status, 'success');
      renderSummary(data);
    } catch (err) {
      EO.toast(err.message, 'error');
      btn.disabled = false;
    }
  });

  // Auto-submitting filters ----------------------------------------------------
  document.addEventListener('change', (e) => {
    const el = e.target.closest('[data-autosubmit]');
    if (el && el.form) el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit();
  });

  // Live search suggestions ---------------------------------------------------
  const searchForm = document.querySelector('[data-suggest]');
  if (searchForm) {
    const input = searchForm.querySelector('input[name="search"]');
    const box = searchForm.querySelector('.search-suggest');
    let timer, controller, active = -1;

    const close = () => { box.classList.remove('show'); box.innerHTML = ''; active = -1; input.setAttribute('aria-expanded', 'false'); };
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) return close();
      timer = setTimeout(async () => {
        if (controller) controller.abort();
        controller = new AbortController();
        try {
          const res = await fetch(EO.urls.suggest + '?q=' + encodeURIComponent(q), { signal: controller.signal });
          const data = await res.json();
          box.innerHTML = '';
          if (!data.results.length) return close();
          data.results.forEach((p) => {
            const a = document.createElement('a');
            a.href = p.url;
            a.setAttribute('role', 'option');
            const img = document.createElement('img');
            img.src = p.image; img.alt = ''; img.loading = 'lazy';
            const text = document.createElement('div');
            const name = document.createElement('div'); name.className = 'fw-semibold'; name.textContent = p.name;
            const meta = document.createElement('small'); meta.className = 'text-muted'; meta.textContent = p.category + ' · ' + EO.formatINR(p.price);
            text.append(name, meta);
            a.append(img, text);
            box.append(a);
          });
          box.classList.add('show');
          input.setAttribute('aria-expanded', 'true');
        } catch (err) { /* aborted or offline */ }
      }, 200);
    });
    input.addEventListener('keydown', (e) => {
      const items = box.querySelectorAll('a');
      if (!items.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        active = (active + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items.forEach((a, i) => a.classList.toggle('active', i === active));
      } else if (e.key === 'Enter' && active >= 0) {
        e.preventDefault();
        window.location.href = items[active].href;
      } else if (e.key === 'Escape') {
        close();
      }
    });
    document.addEventListener('click', (e) => { if (!searchForm.contains(e.target)) close(); });
  }

  // Server-side flash messages --------------------------------------------------
  (window.EO_MESSAGES || []).forEach((m) => EO.toast(m.text, m.level));

  window.EO = EO;
})();
