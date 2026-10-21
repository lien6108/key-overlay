import unittest
from unittest import mock

from key_overlay import tray


class TrayIconTest(unittest.TestCase):
    def test_bundled_icon_asset_is_a_valid_ico(self):
        data = tray.ICON_PATH.read_bytes()

        self.assertEqual(data[:4], b"\x00\x00\x01\x00")
        self.assertGreaterEqual(int.from_bytes(data[4:6], "little"), 1)

    def test_load_small_icon_returns_a_real_icon_handle(self):
        icon = tray.load_small_icon()
        try:
            self.assertTrue(icon)
        finally:
            tray.user32.DestroyIcon(icon)

    @mock.patch.object(tray.shell32, "Shell_NotifyIconW")
    def test_add_retries_when_explorer_rejects_initial_registration(self, notify):
        instance = object.__new__(tray.TrayIcon)
        instance._nid = tray.NOTIFYICONDATAW()
        instance._nid.hWnd = 1
        instance._nid.uID = 1
        instance._nid.uFlags = tray.NIF_MESSAGE | tray.NIF_ICON | tray.NIF_TIP
        instance._nid.hIcon = 1
        instance._stop_requested = mock.Mock()
        instance._stop_requested.wait.return_value = False
        notify.side_effect = [False, True, True]

        self.assertTrue(instance._add_icon_with_retry())
        self.assertEqual(instance._nid.uVersion, tray.NOTIFYICON_VERSION_4)
        self.assertEqual([call.args[0] for call in notify.call_args_list],
                         [tray.NIM_ADD, tray.NIM_ADD, tray.NIM_SETVERSION])


if __name__ == "__main__":
    unittest.main()
