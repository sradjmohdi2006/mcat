"""Clean any remaining mcat.Document entries from the registry."""
import winreg

PROG_ID_KEY = "Software\\Classes\\mcat.Document"


def _delete_key_recursive(root, subkey):
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
            while True:
                try:
                    child = winreg.EnumKey(key, 0)
                    _delete_key_recursive(root, f"{subkey}\\{child}")
                except OSError:
                    break
        winreg.DeleteKey(root, subkey)
    except FileNotFoundError:
        pass


def remove_mcat_progid():
    _delete_key_recursive(winreg.HKEY_CURRENT_USER, PROG_ID_KEY)
    print("Remaining mcat.Document registry entries cleaned.")


if __name__ == "__main__":
    remove_mcat_progid()
