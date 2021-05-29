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
        self._footpedal_keys_down = set()  # Currently held keys.
        self._footpedal_keys = set()  # All keys part of the stroke.
        self._footpedal_key_down_count = 0
        self._ignore_footpedal_stroke = False

        self._update_footpedal_bindings()

    def _suppress_footpedal(self):
        if self._footpedal_capture is None:
            return
        footpedal_keys = self._footpedal_bindings.keys()
        suppressed_keys = footpedal_keys if self._is_suppressed else ()
        self._footpedal_capture.suppress_keyboard(suppressed_keys)

    def _update_footpedal_bindings(self):
        self._footpedal_bindings = dict(self.keymap.get_bindings())
        for key, mapping in list(self._footpedal_bindings.items()):
            if key not in GeminiPrFootpedal.FOOTPEDAL_KEYS:
                del self._footpedal_bindings[key]
                continue
            if 'no-op' == mapping:
                self._footpedal_bindings[key] = None
        self._suppress_footpedal()

    def set_keymap(self, keymap):
        super().set_keymap(keymap)
        self._update_footpedal_bindings()

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
            self._suppress_footpedal()
            self._footpedal_capture.cancel()
            self._footpedal_capture = None
        super().stop_capture()

    def set_suppression(self, enabled):
        self._is_suppressed = enabled
        self._suppress_footpedal()

    def _footkey_down(self, key):
        """Called when a key is pressed."""
        assert key is not None
        self._footpedal_key_down_count += 1
        self._footpedal_keys_down.add(key)
        self._footpedal_keys.add(key)

    def _footkey_up(self, key):
        """Called when a key is released."""
        assert key is not None
        self._footpedal_keys_down.discard(key)
        # A stroke is complete if all pressed keys have been released.
        if self._footpedal_keys_down or not self._footpedal_keys:
            return
        steno_keys = {
            self._footpedal_bindings.get(k)
            for k in self._footpedal_keys
        }
        steno_keys -= {None}
        if steno_keys and not self._ignore_footpedal_stroke:
            self._notify(steno_keys)
        self._footpedal_keys.clear()
        self._footpedal_key_down_count = 0
        self._ignore_footpedal_stroke = False

    def _notify(self, steno_keys):
        if self._footpedal_keys_down:
            steno_keys += {
                self._footpedal_bindings.get(k)
                for k in self._footpedal_keys_down
            }
            self._ignore_footpedal_stroke = True
        super()._notify(steno_keys)
