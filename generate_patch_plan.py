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

    def _device_separator(self):
        """Add a blank row to visually separate device groups."""
        self._blank()

    def generate(self):
        """Generate the complete patch plan."""
        self._header()

        if self.site_type == "small":
            self._generate_small()
        else:
            self._generate_medium()

        return self.rows

    def _generate_small(self):
        """Generate patch plan for small site type."""
        site = self.site
        lab = self.services.get("lab", False)

        sdwan = f"{site}-wan-gw1"
        console = f"{site}-console-server1"

        # WAN gateway connections
        self._entry(sdwan, "gig0/0/3", "GLC-SX-MMD", console, "gig0/0/0", "GLC-SX-MMD", "fiber", "OM4 MMF")

        for floor_info in self.cfg["floors"]:
            floor = floor_info["floor"]
            for stack in floor_info.get("switch_stacks", [{"stack_id": 1}]):
                sw = floor_sw_name(site, floor, stack["stack_id"])
                self._entry(sdwan, "ten0/0/4", "SFP-10Base-SR", sw, "twe1/1/1", "SFP-10Base-SR", "fiber", "OM4 MMF")

        self._entry(sdwan, "gig0/1/0", "RJ 45", f"{site}-ISP", "tbd", "RJ 45", "copper", "Cat 6A")
        self._device_separator()

        # Console server connections
        self._entry(console, "gig0/0/0", "GLC-SX-MMD", sdwan, "gig0/0/3", "GLC-SX-MMD", "fiber", "OM4 MMF")
        self._device_separator()

        # Floor switches
        for floor_info in self.cfg["floors"]:
            floor = floor_info["floor"]
            for stack in floor_info.get("switch_stacks", [{"stack_id": 1}]):
                sw = floor_sw_name(site, floor, stack["stack_id"])
                self._entry(sw, "twe1/1/1", "SFP-10Base-SR", sdwan, "ten0/0/4", "SFP-10Base-SR", "fiber", "OM4 MMF")
                if lab:
                    self._entry(sw, "twe1/1/3", "SFP-10Base-SR", f"{site}-lab-gw1", "ten0/0/4", "SFP-10Base-SR", "fiber", "OM4 MMF")
                self._device_separator()

        # Lab gateway
        if lab:
            lab_gw = f"{site}-lab-gw1"
            for floor_info in self.cfg["floors"]:
                floor = floor_info["floor"]
                for stack in floor_info.get("switch_stacks", [{"stack_id": 1}]):
                    sw = floor_sw_name(site, floor, stack["stack_id"])
                    self._entry(lab_gw, "ten0/0/4", "SFP-10Base-SR", sw, "twe1/1/3", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._device_separator()

    def _generate_medium(self):
        """Generate patch plan for medium site type."""
        site = self.site
        lab = self.services.get("lab", False)
        voice = self.services.get("voice", False)

        sdwan1 = f"{site}-wan-gw1"
        sdwan2 = f"{site}-wan-gw2"
        core1 = f"{site}-core-sw1"
        core2 = f"{site}-core-sw2"
        console = f"{site}-console-server1"

        # --- WAN-GW1 ---
        self._entry(sdwan1, "ten0/0/4", "SFP-10Base-SR", core1, "hun1/0/49", "CVR QSFP28 SFP25G", "fiber", "OM4 MMF")
        self._entry(sdwan1, "ten0/0/5", "SFP-10Base-SR", core2, "hun1/0/49", "CVR QSFP28 SFP25G", "fiber", "OM4 MMF")
        self._entry(sdwan1, "gig0/0/0", "RJ 45", sdwan2, "gig0/0/0", "RJ 45", "copper", "Cat 6A")
        self._entry(sdwan1, "ten0/1/2", "SMF", f"{site}-ISP", "tbd", "SMF", "fiber", "OM4 MMF")
        self._device_separator()

        # --- WAN-GW2 ---
        self._entry(sdwan2, "ten0/0/4", "SFP-10Base-SR", core1, "hun1/0/50", "CVR QSFP28 SFP25G", "fiber", "OM4 MMF")
        self._entry(sdwan2, "ten0/0/5", "SFP-10Base-SR", core2, "hun1/0/50", "CVR QSFP28 SFP25G", "fiber", "OM4 MMF")
        self._entry(sdwan2, "gig0/0/0", "RJ 45", sdwan1, "gig0/0/0", "RJ 45", "copper", "Cat 6A")
        self._entry(sdwan2, "ten0/1/2", "SMF", f"{site}-ISP", "tbd", "SMF", "fiber", "OM4 MMF")
        self._device_separator()

        # --- Core-SW1 ---
        self._entry(core1, "hun1/0/49", "CVR QSFP28 SFP25G", sdwan1, "ten0/0/4", "SFP-10Base-SR", "fiber", "OM4 MMF")
        self._entry(core1, "hun1/0/50", "CVR QSFP28 SFP25G", sdwan2, "ten0/0/4", "SFP-10Base-SR", "fiber", "OM4 MMF")
        self._entry(core1, "twe1/0/15", "SFP-10Base-SR", console, "ten0/0/4", "SFP-10Base-SR", "fiber", "OM4 MMF")

        if lab:
            self._entry(core1, "twe1/0/11", "SFP-10Base-SR", f"{site}-lab-gw1", "ten0/0/0", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._entry(core1, "twe1/0/12", "SFP-10Base-SR", f"{site}-lab-gw2", "ten0/0/0", "SFP-10Base-SR", "fiber", "OM4 MMF")

        if voice:
            self._entry(core1, "twe1/0/13", "SFP-10Base-SR", f"{site}-voice-gw1", "ten0/0/4", "SFP-10Base-SR", "fiber", "OM4 MMF")

        # Floor switch uplinks from core1
        core_port = 20
        for floor_info in self.cfg["floors"]:
            floor = floor_info["floor"]
            for stack in floor_info.get("switch_stacks", [{"stack_id": 1}]):
                sw = floor_sw_name(site, floor, stack["stack_id"])
                self._entry(core1, f"twe1/0/{core_port}", "SFP-10/25GBase-CSR", sw, "twe1/1/1", "SFP-10/25GBase-CSR", "fiber", "OM4 MMF")
                core_port += 1

        # Core cross-links
        self._entry(core1, "twe1/0/3", "SFP-10/25GBase-CSR", core2, "twe1/0/3", "SFP-10/25GBase-CSR", "fiber", "OM4 MMF")
        self._entry(core1, "twe1/0/4", "SFP-10/25GBase-CSR", core2, "twe1/0/4", "SFP-10/25GBase-CSR", "fiber", "OM4 MMF")
        self._device_separator()

        # --- Core-SW2 ---
        self._entry(core2, "hun1/0/49", "CVR QSFP28 SFP25G", sdwan1, "ten0/0/5", "SFP-10Base-SR", "fiber", "OM4 MMF")
        self._entry(core2, "hun1/0/50", "CVR QSFP28 SFP25G", sdwan2, "ten0/0/5", "SFP-10Base-SR", "fiber", "OM4 MMF")
        self._entry(core2, "twe1/0/15", "SFP-10Base-SR", console, "ten0/0/5", "SFP-10Base-SR", "fiber", "OM4 MMF")

        if lab:
            self._entry(core2, "twe1/0/11", "SFP-10Base-SR", f"{site}-lab-gw1", "ten0/0/1", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._entry(core2, "twe1/0/12", "SFP-10Base-SR", f"{site}-lab-gw2", "ten0/0/1", "SFP-10Base-SR", "fiber", "OM4 MMF")

        if voice:
            self._entry(core2, "twe1/0/13", "SFP-10Base-SR", f"{site}-voice-gw1", "ten0/0/5", "SFP-10Base-SR", "fiber", "OM4 MMF")

        # Floor switch uplinks from core2
        core_port = 20
        for floor_info in self.cfg["floors"]:
            floor = floor_info["floor"]
            for stack in floor_info.get("switch_stacks", [{"stack_id": 1}]):
                sw = floor_sw_name(site, floor, stack["stack_id"])
                self._entry(core2, f"twe1/0/{core_port}", "SFP-10/25GBase-CSR", sw, "twe2/1/1", "SFP-10/25GBase-CSR", "fiber", "OM4 MMF")
                core_port += 1

        self._entry(core2, "twe1/0/3", "SFP-10Base-SR", core1, "twe1/0/3", "SFP-10Base-SR", "fiber", "OM4 MMF")
        self._entry(core2, "twe1/0/4", "SFP-10Base-SR", core1, "twe1/0/4", "SFP-10Base-SR", "fiber", "OM4 MMF")
        self._device_separator()

        # --- Console Server ---
        self._entry(console, "ten0/0/4", "SFP-10Base-SR", core1, "twe1/0/15", "SFP-10Base-SR", "fiber", "OM4 MMF")
        self._entry(console, "ten0/0/5", "SFP-10Base-SR", core2, "twe1/0/15", "SFP-10Base-SR", "fiber", "OM4 MMF")
        self._device_separator()

        # --- Lab Gateways ---
        if lab:
            lab1 = f"{site}-lab-gw1"
            lab2 = f"{site}-lab-gw2"
            self._entry(lab1, "ten0/0/0", "SFP-10Base-SR", core1, "twe1/0/11", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._entry(lab1, "ten0/0/1", "SFP-10Base-SR", core2, "twe1/0/11", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._entry(lab1, "ten0/0/2", "SFP-10Base-SR", lab2, "ten0/0/2", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._device_separator()

            self._entry(lab2, "ten0/0/0", "SFP-10Base-SR", core1, "twe1/0/12", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._entry(lab2, "ten0/0/1", "SFP-10Base-SR", core2, "twe1/0/12", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._entry(lab2, "ten0/0/2", "SFP-10Base-SR", lab1, "ten0/0/2", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._device_separator()

        # --- Voice Gateway ---
        if voice:
            voice_gw = f"{site}-voice-gw1"
            self._entry(voice_gw, "ten0/0/4", "SFP-10Base-SR", core1, "twe1/0/13", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._entry(voice_gw, "ten0/0/5", "SFP-10Base-SR", core2, "twe1/0/13", "SFP-10Base-SR", "fiber", "OM4 MMF")
            self._device_separator()

        # --- Floor Switches ---
        core_port = 20
        for floor_info in self.cfg["floors"]:
            floor = floor_info["floor"]
            for stack in floor_info.get("switch_stacks", [{"stack_id": 1}]):
                sw = floor_sw_name(site, floor, stack["stack_id"])
                self._entry(sw, "twe1/1/1", "SFP-10/25GBase-CSR", core1, f"twe1/0/{core_port}", "SFP-10/25GBase-CSR", "fiber", "OM4 MMF")
                self._entry(sw, "twe2/1/1", "SFP-10/25GBase-CSR", core2, f"twe1/0/{core_port}", "SFP-10/25GBase-CSR", "fiber", "OM4 MMF")
                core_port += 1
                self._device_separator()


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
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"Patch plan generated: {output_path}")


if __name__ == "__main__":
    main()
