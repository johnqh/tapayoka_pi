"""Tests for LED/relay service (mock mode - no RPi.GPIO)."""

import time

from src.led_service import LEDService


def test_led_starts_inactive():
    led = LEDService(pin=17)
    assert not led.is_active


def test_led_activate():
    led = LEDService(pin=17)
    led.activate()
    assert led.is_active


def test_led_deactivate():
    led = LEDService(pin=17)
    led.activate()
    led.deactivate()
    assert not led.is_active


def test_led_activate_with_duration():
    """Activate with a short duration and verify auto-deactivation."""
    led = LEDService(pin=17)
    led.activate(duration_seconds=1)
    assert led.is_active
    time.sleep(1.5)
    assert not led.is_active


def test_led_reactivate_cancels_previous_timer():
    """Re-activating should cancel any pending auto-deactivation."""
    led = LEDService(pin=17)
    led.activate(duration_seconds=1)
    # Re-activate without duration (indefinite)
    led.activate()
    time.sleep(1.5)
    # Should still be active since we re-activated without duration
    assert led.is_active
    led.deactivate()


def test_led_cleanup():
    led = LEDService(pin=17)
    led.activate()
    led.cleanup()
    assert not led.is_active


def test_led_multiple_deactivate():
    """Calling deactivate multiple times should be safe."""
    led = LEDService(pin=17)
    led.deactivate()
    led.deactivate()
    assert not led.is_active
