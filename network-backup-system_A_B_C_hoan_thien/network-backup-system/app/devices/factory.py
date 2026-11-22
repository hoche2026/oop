from app.contracts import DeviceInfo, InventoryError
from app.devices.cisco_ios import CiscoIOSDevice
from app.devices.cisco_ios_switch import CiscoIOSSwitchDevice
from app.devices.mikrotik import MikroTikDevice


class DeviceFactory:
    _registry = {
        "cisco_ios": CiscoIOSDevice,
        "mikrotik_routeros": MikroTikDevice,
    }

    @classmethod
    def create(cls, info: DeviceInfo):
        if not isinstance(info, DeviceInfo):
            raise InventoryError("Thong tin phai la DeviceInfo.")

        device_class = cls._registry.get(info.platform)

        if device_class is None:
            raise InventoryError(
                f"Chua ho tro platform: {info.platform}"
            )

        if info.platform == "cisco_ios" and info.role == "switch":
            device_class = CiscoIOSSwitchDevice

        return device_class(info)
