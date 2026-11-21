#!/usr/bin/env python3
"""Controles nativos ReyTV: lista cerrada de operaciones, sin shell ni privilegios root.

NetworkManager y BlueZ deciden los permisos de la sesión local (polkit).
Nunca se devuelven contraseñas ni se guardan en logs.
"""
import os
import ipaddress
import re
import shutil
import subprocess

MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class NativeError(Exception):
    pass


def _run(command, timeout=12):
    if not shutil.which(command[0]):
        raise NativeError(f"No está instalada la herramienta {command[0]}.")
    # Conservar XDG_RUNTIME_DIR y DBUS_SESSION_BUS_ADDRESS para PipeWire/BlueZ/NM.
    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LANG": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"})
    try:
        result = subprocess.run(
            command, text=True, capture_output=True, timeout=timeout,
            check=False, env=env,
        )
    except subprocess.TimeoutExpired:
        raise NativeError("La operación tardó demasiado. Prueba nuevamente.") from None
    if result.returncode:
        # Algunas herramientas podrían incluir la clave en errores. No propagar stderr.
        raise NativeError(f"No se pudo completar la operación ({command[0]}). Revisa permisos y dispositivo.")
    return result.stdout


def _split_nm(text):
    """Parsear campos nmcli -t, que escapan : y \\ en SSID y nombres."""
    values, word, escape = [], [], False
    for ch in text:
        if escape:
            word.append(ch)
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == ":":
            values.append("".join(word))
            word = []
        else:
            word.append(ch)
    if escape:
        word.append("\\")
    values.append("".join(word))
    return values


def _wifi_iface():
    data = _run(["nmcli", "-t", "-e", "yes", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    for line in data.splitlines():
        cols = _split_nm(line)
        if len(cols) >= 4 and cols[1] == "wifi":
            return cols[0], cols[2], cols[3]
    raise NativeError("No se detectó adaptador Wi-Fi gestionado por NetworkManager.")


def wifi_status(scan=False):
    try:
        radio = _run(["nmcli", "radio", "wifi"]).strip().lower()
        dev, state, connected = _wifi_iface()
        networks = []
        if radio == "enabled":
            cmd = ["nmcli", "-t", "-e", "yes", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                   "device", "wifi", "list", "ifname", dev, "--rescan", "yes" if scan else "no"]
            raw = _run(cmd, 22 if scan else 8)
            found = set()
            for line in raw.splitlines():
                cols = _split_nm(line)
                if len(cols) < 4 or not cols[1] or cols[1] in found:
                    continue
                found.add(cols[1])
                try:
                    strength = min(100, max(0, int(cols[2])))
                except ValueError:
                    strength = 0
                networks.append({"name": cols[1], "signal": strength,
                                 "security": cols[3], "active": cols[0] == "*"})
            networks.sort(key=lambda n: (not n["active"], -n["signal"]))
        ip = ""
        if state.startswith("connected"):
            try:
                addresses = _run(["nmcli", "-g", "IP4.ADDRESS", "device", "show", dev], 5)
                for line in addresses.splitlines():
                    try:
                        ip = str(ipaddress.IPv4Interface(line.strip()).ip)
                        break
                    except ValueError:
                        continue
            except NativeError:
                pass
        active_ssid = next((net["name"] for net in networks if net["active"]), "")
        return {"available": True, "enabled": radio == "enabled",
                "connected": (active_ssid or connected) if state.startswith("connected") else "",
                "interface": dev, "ipv4": ip, "networks": networks[:30]}
    except NativeError as exc:
        return {"available": False, "error": str(exc), "networks": []}


def bluetooth_status(scan=False):
    if not shutil.which("bluetoothctl"):
        return {"available": False, "error": "Bluetooth no está instalado.", "devices": []}
    try:
        info = _run(["bluetoothctl", "show"], 8)
        if not re.search(r"Controller\s+[0-9A-Fa-f:]{17}", info):
            raise NativeError("No se detectó adaptador Bluetooth.")
        powered = bool(re.search(r"^\s*Powered:\s+yes", info, re.M))
        if scan and powered:
            # Escaneo limitado. bluez puede devolver código de salida distinto al acabar.
            try:
                subprocess.run(["bluetoothctl", "--timeout", "8", "scan", "on"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=11, check=False)
            except subprocess.TimeoutExpired:
                pass
        devices = []
        for line in _run(["bluetoothctl", "devices"], 7).splitlines()[:32]:
            match = re.match(r"^Device\s+([0-9A-Fa-f:]{17})\s+(.+)$", line)
            if not match or not MAC.fullmatch(match.group(1)):
                continue
            addr, name = match.groups()
            try:
                details = _run(["bluetoothctl", "info", addr], 3)
            except NativeError:
                details = ""
            devices.append({
                "address": addr.upper(), "name": name[:90],
                "paired": bool(re.search(r"^\s*Paired:\s+yes", details, re.M)),
                "connected": bool(re.search(r"^\s*Connected:\s+yes", details, re.M)),
            })
        return {"available": True, "enabled": powered, "devices": devices[:24]}
    except NativeError as exc:
        return {"available": False, "error": str(exc), "devices": []}


def sound_status():
    try:
        output = _run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], 5)
        match = re.search(r"Volume:\s+([0-9.]+)", output)
        if not match:
            raise NativeError("No se detectó salida de audio.")
        return {"available": True, "percent": min(100, round(float(match.group(1)) * 100)),
                "muted": "[MUTED]" in output}
    except (NativeError, ValueError) as exc:
        return {"available": False, "error": str(exc)}


def status(scan=None):
    return {"wifi": wifi_status(scan == "wifi"), "bluetooth": bluetooth_status(scan == "bluetooth"),
            "sound": sound_status()}


def act(operation, args):
    if not isinstance(args, dict):
        raise NativeError("Parámetros no válidos.")
    # Bloquear campos desconocidos para cada operación.
    fields = {
        "wifi_toggle": {"enabled"},
        "wifi_connect": {"ssid", "password"},
        "wifi_disconnect": set(),
        "bt_toggle": {"enabled"},
        "bt_pair": {"address"},
        "bt_connect": {"address"},
        "bt_disconnect": {"address"},
        "sound_volume": {"percent"},
        "sound_mute": {"muted"},
    }
    if operation not in fields or set(args) != fields[operation]:
        raise NativeError("Acción no permitida o parámetros incompletos.")
    if operation == "wifi_toggle":
        if type(args["enabled"]) is not bool:
            raise NativeError("Valor Wi-Fi no válido.")
        _run(["nmcli", "radio", "wifi", "on" if args["enabled"] else "off"], 10)
    elif operation == "wifi_connect":
        name, password = args["ssid"], args["password"]
        if not isinstance(name, str) or not 1 <= len(name.encode("utf-8")) <= 32 or "\x00" in name or name.startswith("-"):
            raise NativeError("Nombre de red no válido.")
        if not isinstance(password, str) or len(password) > 64 or "\x00" in password:
            raise NativeError("Clave Wi-Fi no válida.")
        iface, _, _ = _wifi_iface()
        cmd = ["nmcli", "--wait", "35", "device", "wifi", "connect", name]
        if password:
            if not (8 <= len(password) <= 63 or len(password) == 64 and re.fullmatch("[0-9A-Fa-f]{64}", password)):
                raise NativeError("La clave WPA debe tener 8-63 caracteres, o 64 dígitos hexadecimales.")
            cmd += ["password", password]
        cmd += ["ifname", iface, "private", "yes"]
        _run(cmd, 42)
    elif operation == "wifi_disconnect":
        iface, _, _ = _wifi_iface()
        _run(["nmcli", "device", "disconnect", iface], 12)
    elif operation == "bt_toggle":
        if type(args["enabled"]) is not bool:
            raise NativeError("Valor Bluetooth no válido.")
        _run(["bluetoothctl", "power", "on" if args["enabled"] else "off"], 9)
    elif operation in ("bt_pair", "bt_connect", "bt_disconnect"):
        addr = args["address"]
        if not isinstance(addr, str) or not MAC.fullmatch(addr):
            raise NativeError("Dirección Bluetooth inválida.")
        if operation == "bt_pair":
            # Just Works, sin código de emparejamiento; no cubre PIN o confirmación.
            _run(["bluetoothctl", "--agent=NoInputNoOutput", "pair", addr], 32)
            _run(["bluetoothctl", "trust", addr], 8)
            _run(["bluetoothctl", "connect", addr], 20)
        else:
            _run(["bluetoothctl", "connect" if operation == "bt_connect" else "disconnect", addr], 18)
    elif operation == "sound_volume":
        amount = args["percent"]
        if type(amount) is not int or not 0 <= amount <= 100:
            raise NativeError("Volumen fuera de rango.")
        _run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{amount}%"], 5)
    elif operation == "sound_mute":
        if type(args["muted"]) is not bool:
            raise NativeError("Silencio no válido.")
        _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if args["muted"] else "0"], 5)
    return {"ok": True}
