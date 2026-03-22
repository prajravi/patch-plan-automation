# Patch Plan Automation

Standalone tool that generates a CSV patch plan defining all physical cable connections between network devices at a site.

## Folder Structure

```
patch-plan-automation/
├── generate_patch_plan.py        # Main script
├── config/
│   ├── connectivity.yaml         # Connection templates, port mappings, cable specs
│   └── site_types.yaml           # Device roles, hardware models per site type
├── inputs/
│   ├── nyc_input.yaml            # Medium site example (New York)
│   └── bgl_input.yaml            # Small site example (Bangalore)
└── output/                       # Generated CSV output files
```

## Quick Start

```bash
cd patch-plan-automation
python3 generate_patch_plan.py inputs/nyc_input.yaml    # Medium site
python3 generate_patch_plan.py inputs/bgl_input.yaml    # Small site
```

Output goes to `output/<site>-patch-plan.csv`.

## Prerequisites

- Python 3.6+
- PyYAML (`pip install pyyaml`)

## What It Produces

The patch plan CSV has 8 columns:

| Column | Content |
|--------|---------|
| **From** | Source device name (shown once per device group) |
| **Interface** | Source port/interface identifier |
| **Media Type** | SFP/optic module on source side |
| **To** | Destination device name |
| **Interface** | Destination port/interface identifier |
| **Media Type** | SFP/optic module on destination side |
| **Notes** | Cable category (fiber / copper) |
| **Cable** | Cable specification (OM4 MMF, Cat 6A, etc.) |

## Input YAML

Same input format as the address plan generator. Key fields used by the patch plan:

```yaml
site: nyc                          # Site identifier (used in device names)
site_type: medium                  # small | medium

services:
  lab: true                        # Deploy lab gateway(s)
  voice: true                      # Deploy voice gateway (medium only)

floors:
  - floor: "11"
    switch_stacks:
      - stack_id: 1
        members: 2
```

The `network` section (IP addressing) is ignored by the patch plan — it only uses site identity, services, and floor/stack definitions.

## Site Types

### Small
- `wan-gw1` → `floor-sw` (fiber, 10G)
- `wan-gw1` → `console-server1` (fiber)
- `wan-gw1` → ISP (copper)
- `floor-sw` → `lab-gw1` (fiber, optional)

### Medium
- `wan-gw1/2` → `core-sw1/2` (fiber, 10G to 100G breakout)
- `wan-gw1` ↔ `wan-gw2` (copper cross-connect)
- `wan-gw1/2` → ISP (fiber)
- `core-sw1` ↔ `core-sw2` (fiber cross-links ×2)
- `core-sw1/2` → `console-server1` (fiber, dual-homed)
- `core-sw1/2` → `lab-gw1/2` (fiber, dual-homed, optional)
- `lab-gw1` ↔ `lab-gw2` (fiber cross-link, optional)
- `core-sw1/2` → `voice-gw1` (fiber, dual-homed, optional)
- `core-sw1/2` → `floor-sw` (fiber, 25G, dual-homed)

### Connection Symmetry

Every connection appears twice — once from each side. Each device's section is a complete wiring checklist for that device.

### Dynamic Port Allocation

Floor switch uplinks on core switches use sequential ports starting at `twe1/0/20`, incrementing for each floor/stack.

## Naming Convention

| Role | Device Name Pattern |
|------|-------------------|
| WAN Gateway | `{site}-wan-gw{1\|2}` |
| Core Switch | `{site}-core-sw{1\|2}` |
| Console Server | `{site}-console-server1` |
| Floor Switch | `{site}-{floor}-sw{stack_id}` |
| Lab Gateway | `{site}-lab-gw{1\|2}` |
| Voice Gateway | `{site}-voice-gw1` |

## Configuration Files

| File | Purpose |
|------|---------|
| `config/connectivity.yaml` | Connection templates with port mappings, media types, cable specs per site type |
| `config/site_types.yaml` | Device roles, hardware models, redundancy levels, port counts per site type |
