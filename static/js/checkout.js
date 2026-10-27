/* Payment step: real Razorpay Checkout, or the demo-mode "payment paused" screen. */
(function () {
  'use strict';
  const EO = window.EO;

  EO.setBusy = function (btn, busy) {
    if (!btn) return;
    btn.disabled = busy;
    const spinner = btn.querySelector('.spinner-border');
    const label = btn.querySelector('.btn-label');
    if (spinner) spinner.classList.toggle('d-none', !busy);
    if (label) label.classList.toggle('opacity-50', busy);
  };

  function showPaused(payment) {
    const modalEl = document.getElementById('paymentPausedModal');
    modalEl.querySelector('[data-paused-order]').textContent = payment.order_number;
    modalEl.querySelector('[data-paused-amount]').textContent = EO.formatINR(payment.amount);
    modalEl.querySelector('[data-paused-link]').href = payment.order_url;
    modalEl.addEventListener('hidden.bs.modal', () => { window.location.href = payment.order_url; }, { once: true });
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  function openRazorpay(payment, onDone) {
    if (typeof window.Razorpay !== 'function') {
      EO.toast('Payment window failed to load. Check your connection and try again.', 'error');
      onDone();
      return;
    }
    const rzp = new window.Razorpay({
      key: payment.key,
      amount: payment.amount,
      currency: payment.currency,
      name: payment.name,
      description: payment.description,
      order_id: payment.razorpay_order_id,
      prefill: payment.prefill,
      theme: { color: '#4f46e5' },
      handler: async (response) => {
        try {
          const result = await EO.post(payment.verify_url, response);
          window.location.href = result.redirect;
        } catch (err) {
          EO.toast(err.message, 'error');
          window.location.href = payment.order_url;
        }
      },
      modal: {
        ondismiss: () => {
          EO.toast('Payment cancelled. Your order is saved — you can pay from My orders.', 'info');
          onDone();
        },
      },
    });
    rzp.on('payment.failed', (resp) => {
      EO.post(payment.failed_url, { order_number: payment.order_number, reason: resp.error && resp.error.description }).catch(() => {});
      EO.toast((resp.error && resp.error.description) || 'Payment failed. Please try again.', 'error');
    });
    rzp.open();
  }

  EO.startPayment = function (payment, onDone) {
    onDone = onDone || function () {};
    if (payment.mode === 'demo') {
      showPaused(payment);
      onDone();
    } else {
      openRazorpay(payment, onDone);
    }
  };

  // "Pay now" buttons on order pages
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-pay-order]');
    if (!btn) return;
    e.preventDefault();
    EO.setBusy(btn, true);
    try {
      const data = await EO.post(btn.dataset.payOrder, {});
      EO.startPayment(data.payment, () => EO.setBusy(btn, false));
    } catch (err) {
      EO.toast(err.message, 'error');
      EO.setBusy(btn, false);
    }
  });
})();
