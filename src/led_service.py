"""GPIO LED/relay control service."""

import threading

try:
    import RPi.GPIO as GPIO

    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[LED] RPi.GPIO not available - running in mock mode")


class LEDService:
    """Controls GPIO pins for relay/LED output."""

    def __init__(self, pin: int = 17) -> None:
        self._pin = pin
        self._active = False
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self._pin, GPIO.OUT)
            GPIO.output(self._pin, GPIO.LOW)
            print(f"[LED] Initialized GPIO pin {self._pin}")
        else:
            print(f"[LED] Mock mode - pin {self._pin}")

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self, duration_seconds: int = 0) -> None:
        """Activate relay. If duration > 0, auto-deactivate after duration."""
        with self._lock:
            self._cancel_timer()
            if GPIO_AVAILABLE:
                GPIO.output(self._pin, GPIO.HIGH)
            self._active = True
            print(f"[LED] Relay ACTIVATED (pin {self._pin})")

            if duration_seconds > 0:
                self._timer = threading.Timer(duration_seconds, self.deactivate)
                self._timer.daemon = True
                self._timer.start()
                print(f"[LED] Auto-deactivate in {duration_seconds}s")

    def deactivate(self) -> None:
        """Deactivate relay."""
        with self._lock:
            self._cancel_timer()
            if GPIO_AVAILABLE:
                GPIO.output(self._pin, GPIO.LOW)
            self._active = False
            print(f"[LED] Relay DEACTIVATED (pin {self._pin})")

    def _cancel_timer(self) -> None:
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
        self._timer = None

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        self.deactivate()
        if GPIO_AVAILABLE:
            GPIO.cleanup(self._pin)
            print("[LED] GPIO cleaned up")
