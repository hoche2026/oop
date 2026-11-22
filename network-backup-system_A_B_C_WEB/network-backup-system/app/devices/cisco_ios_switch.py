from app.devices.cisco_ios import CiscoIOSDevice


class CiscoIOSSwitchDevice(CiscoIOSDevice):
    _restore_file_system = "unix:"

    def get_facts(self):
        facts = super().get_facts()

        facts["vlans"] = self._collect_section(
            "show vlan brief",
            lambda output: self._parse_table(
                "show vlan",
                output,
            ),
        )

        facts["mac_table"] = self._collect_section(
            "show mac address-table",
            lambda output: self._parse_table(
                "show mac address-table",
                output,
            ),
        )

        return facts
