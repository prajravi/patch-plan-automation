#!/usr/bin/env python3
"""
Patch Plan Generator

Generates a CSV patch plan for a site based on YAML input configuration.
The patch plan defines all physical cable connections between devices.

Usage:
    python3 generate_patch_plan.py inputs/bgl_input.yaml
    python3 generate_patch_plan.py inputs/nyc_input.yaml
"""

import csv
import os
import sys

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_config():
    """Load connectivity and site type configuration."""
    conn_cfg = load_yaml(os.path.join(SCRIPT_DIR, "config", "connectivity.yaml"))
    site_types_cfg = load_yaml(os.path.join(SCRIPT_DIR, "config", "site_types.yaml"))
    return conn_cfg, site_types_cfg


def floor_sw_name(site, floor, stack_id):
    """Generate floor switch name."""
    return f"{site}-{floor}-sw{stack_id}"


def device_name(site, role, dev_id):
    """Generate a site-prefixed device name from a connectivity role and ID."""
    if role == "ISP":
        return f"{site}-ISP"
    role_map = {
        "wan_gw": "wan-gw",
        "core_sw": "core-sw",
        "console_server": "console-server",
        "lab_gw": "lab-gw",
        "voice_gw": "voice-gw",
    }
    return f"{site}-{role_map[role]}{dev_id}"


class PatchPlan:
    def __init__(self, input_cfg):
        self.cfg = input_cfg
        self.site = input_cfg["site"]
        self.site_type = input_cfg["site_type"]
        self.conn_cfg, self.site_types_cfg = load_config()
        self.services = input_cfg.get("services", {})

        self.rows = []
        # Track entries per device so we can group them (first row shows device name)
        self.current_device = None

    def _header(self):
        self.rows.append(["From", "Interface", "Media Type", "To", "Interface", "Media Type", "Notes", "Cable"])

    def _entry(self, from_dev, from_port, from_media, to_dev, to_port, to_media, notes, cable):
        """Add a patch entry. If from_dev is same as previous, leave From column empty."""
        if from_dev == self.current_device:
            self.rows.append(["", from_port, from_media, to_dev, to_port, to_media, notes, cable])
        else:
            self.current_device = from_dev
            self.rows.append([from_dev, from_port, from_media, to_dev, to_port, to_media, notes, cable])

    def _blank(self):
        self.rows.append(["", "", "", "", "", "", "", ""])
        self.current_device = None

    def generate(self):
        """Generate the complete patch plan from connectivity.yaml."""
        self._header()
        connections = self._connections_for_site()
        for device in self._device_order(connections):
            for connection in connections:
                if connection["from_device"] == device:
                    self._entry(
                        device, connection["from_port"], connection["from_media"],
                        connection["to_device"], connection["to_port"], connection["to_media"],
                        connection["cable_type"], connection["cable"],
                    )
                elif connection["to_device"] == device:
                    self._entry(
                        device, connection["to_port"], connection["to_media"],
                        connection["from_device"], connection["from_port"], connection["from_media"],
                        connection["cable_type"], connection["cable"],
                    )
            self._blank()
        return self.rows

    def _connections_for_site(self):
        """Expand static and floor-stack links from connectivity.yaml."""
        topology = self.conn_cfg[self.site_type]
        connections = []
        for connection in topology["connections"]:
            if not self._connection_enabled(connection):
                continue
            contexts = self._floor_contexts() if "floor_sw" in (
                connection["from_role"], connection["to_role"]
            ) else [{}]
            for context in contexts:
                connections.append(self._materialize_connection(connection, context))
        connections.extend(self._switch_uplink_connections(topology))
        return connections

    def _connection_enabled(self, connection):
        condition = connection.get("condition")
        if not condition:
            return True
        service = condition[:-8] if condition.endswith("_enabled") else condition
        return self.services.get(service, False)

    def _floor_contexts(self):
        return [
            {"floor": floor_info["floor"], "stack_id": stack["stack_id"]}
            for floor_info in self.cfg["floors"]
            for stack in floor_info.get("switch_stacks", [{"stack_id": 1}])
        ]

    def _device_for(self, role, dev_id, context):
        if role == "floor_sw":
            return floor_sw_name(self.site, context["floor"], context["stack_id"])
        return device_name(self.site, role, dev_id)

    def _materialize_connection(self, connection, context):
        return {
            "from_device": self._device_for(connection["from_role"], connection["from_id"], context),
            "from_port": connection["from_port"],
            "from_media": connection["from_media"],
            "to_device": self._device_for(connection["to_role"], connection["to_id"], context),
            "to_port": connection["to_port"],
            "to_media": connection["to_media"],
            "cable_type": connection["cable_type"],
            "cable": connection["cable"],
        }

    def _switch_uplink_connections(self, topology):
        """Create the dynamic core-to-floor links defined by switch_uplinks."""
        uplinks = topology.get("switch_uplinks")
        if not uplinks:
            return []
        connections = []
        for offset, context in enumerate(self._floor_contexts()):
            core_port = f"twe1/0/{uplinks['core_base_port'] + offset}"
            floor_switch = self._device_for("floor_sw", 1, context)
            for core_id, floor_port in ((1, uplinks["sw_member1_port"]), (2, uplinks["sw_member2_port"])):
                connections.append({
                    "from_device": self._device_for("core_sw", core_id, {}),
                    "from_port": core_port,
                    "from_media": uplinks["media"],
                    "to_device": floor_switch,
                    "to_port": floor_port,
                    "to_media": uplinks["media"],
                    "cable_type": uplinks["cable_type"],
                    "cable": uplinks["cable"],
                })
        return connections

    @staticmethod
    def _device_order(connections):
        """Return non-ISP devices in first-seen order for grouped output."""
        devices = []
        for connection in connections:
            for device in (connection["from_device"], connection["to_device"]):
                if device.endswith("-ISP") or device in devices:
                    continue
                devices.append(device)
        return devices


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_patch_plan.py <input_yaml>")
        print("Example: python3 generate_patch_plan.py inputs/nyc_input.yaml")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.isabs(input_path):
        input_path = os.path.join(SCRIPT_DIR, input_path)

    input_cfg = load_yaml(input_path)
    site = input_cfg["site"]

    plan = PatchPlan(input_cfg)
    rows = plan.generate()

    output_dir = os.path.join(SCRIPT_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{site}-patch-plan.csv")

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerows(rows)

    print(f"Patch plan generated: {output_path}")


if __name__ == "__main__":
    main()
