"""Razorpay integration (REST API + HMAC signature checks, no SDK needed)."""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

RAZORPAY_API = 'https://api.razorpay.com/v1'


class PaymentError(Exception):
    pass


def is_live_payment_enabled():
    """Real Razorpay checkout runs only with keys configured and demo mode off."""
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET and not settings.PAYMENT_DEMO_MODE)


def create_razorpay_order(order):
    try:
        response = requests.post(
            f'{RAZORPAY_API}/orders',
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json={
                'amount': order.amount_paise,
                'currency': 'INR',
                'receipt': order.order_number,
                'notes': {'order_number': order.order_number},
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.exception('Razorpay order creation failed for %s', order.order_number)
        raise PaymentError('Payment gateway is unreachable. Please try again.') from exc

    if response.status_code >= 400:
        logger.error('Razorpay rejected order %s: %s', order.order_number, response.text[:500])
        raise PaymentError('Payment gateway rejected the request. Please try again.')
    return response.json()['id']


def _hmac_hex(secret, message):
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_payment_signature(razorpay_order_id, razorpay_payment_id, signature):
    if not (settings.RAZORPAY_KEY_SECRET and razorpay_order_id and razorpay_payment_id and signature):
        return False
    expected = _hmac_hex(settings.RAZORPAY_KEY_SECRET, f'{razorpay_order_id}|{razorpay_payment_id}'.encode())
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(body, signature):
    if not (settings.RAZORPAY_WEBHOOK_SECRET and signature):
        return False
    expected = _hmac_hex(settings.RAZORPAY_WEBHOOK_SECRET, body)
    return hmac.compare_digest(expected, signature)
