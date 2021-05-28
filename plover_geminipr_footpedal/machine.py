import binascii

from plover import _
from plover.machine.keyboard import Keyboard
from plover.machine.geminipr import GeminiPr, STENO_KEY_CHART, BYTES_PER_STROKE

from plover_keyboard_plus.machine import KeyboardPlus, KeyboardPlusCapture

# i18n: Machine name.
_._('Gemini PR Footpedal')


class GeminiPrFootpedal(GeminiPr):
    FOOTPEDAL_KEYS_LAYOUT = '''
        F13 F14 F15 F16
    '''
    FOOTPEDAL_KEYS = ('F13', 'F14', 'F15', 'F16')
    KEYS_LAYOUT = GeminiPr.KEYS_LAYOUT + FOOTPEDAL_KEYS_LAYOUT

    # Ordinarily, we would fall back on Gemini PR here
    # Due to the way the fallback code in plover.config::system_keymap_option::build_keymap
    #   works, this will remove all of the extra keys prodided above.
    # KEYMAP_MACHINE_TYPE = 'Gemini PR'

    def __init__(self, params):
        super().__init__(params)
        self._footpedal_capture = None
        self._is_suppressed = False
        # Currently held keys.
        self._down_keys = set()
        # All keys part of the stroke.
        self._stroke_keys = set()
        self._last_stroke_key_down_count = 0
        self._stroke_key_down_count = 0
        self._update_bindings()

    def _suppress(self):
        if self._footpedal_capture is None:
            return
        suppressed_keys = GeminiPrFootpedal.FOOTPEDAL_KEYS if self._is_suppressed else ()
        self._footpedal_capture.suppress_keyboard(suppressed_keys)

    def _update_bindings(self):
        self._bindings = dict(self.keymap.get_bindings())
        for key, mapping in list(self._bindings.items()):
            if 'no-op' == mapping:
                self._bindings[key] = None
        self._suppress()

    def set_keymap(self, keymap):
        super().set_keymap(keymap)
        self._update_bindings()

    def start_capture(self):
        try:
            self._footpedal_capture = KeyboardPlusCapture()
            self._footpedal_capture.key_down = self._footkey_down
            self._footpedal_capture.key_up = self._footkey_up
            self._footpedal_capture.start()
        except:
            self._error()
            raise

        super().start_capture()

    def stop_capture(self):
        if self._footpedal_capture is not None:
            self._is_suppressed = False
            self._suppress()
            self._footpedal_capture.cancel()
            self._footpedal_capture = None

        super().stop_capture()

    def set_suppression(self, enabled):
        self._is_suppressed = enabled
        self._suppress()

    def _footkey_down(self, key):
        """Called when a key is pressed."""
        assert key is not None
        self._stroke_key_down_count += 1
        self._down_keys.add(key)
        self._stroke_keys.add(key)

    def _footkey_up(self, key):
        """Called when a key is released."""
        assert key is not None
        self._down_keys.discard(key)
        # A stroke is complete if all pressed keys have been released.
        if self._down_keys or not self._stroke_keys:
            return
        self._last_stroke_key_down_count = self._stroke_key_down_count
        steno_keys = {self._bindings.get(k) for k in self._stroke_keys}
        steno_keys -= {None}
        if steno_keys:
            self._notify(steno_keys)
        self._stroke_keys.clear()
        self._stroke_key_down_count = 0

    def _notify(self, steno_keys):

        super()._notify(steno_keys)

    def run(self):
        """Overrides base class run method. Do not call directly."""
        self._ready()
        for packet in self._iter_packets(BYTES_PER_STROKE):
            if not (packet[0] & 0x80) or sum(b & 0x80 for b in packet[1:]):
                log.error('discarding invalid packet: %s',
                          binascii.hexlify(packet))
                continue
            steno_keys = []
            for i, b in enumerate(packet):
                for j in range(1, 8):
                    if (b & (0x80 >> j)):
                        steno_keys.append(STENO_KEY_CHART[i * 7 + j - 1])
            steno_keys = self.keymap.keys_to_actions(steno_keys)
            if steno_keys:
                self._notify(steno_keys)

