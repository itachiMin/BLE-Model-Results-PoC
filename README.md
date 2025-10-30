# BLE Secure Connections Pairing Formal Verification

This repository contains the formal models, verification scripts, and attack implementations for analyzing the security of BLE Secure Connections pairing protocols.

## Repository Structure

- **`./Attack/`** - Firmware and tools for implementing PE confusion attacks
- **`./ExpCode/`** - Tamarin prover formal models
- **`./ExpRun/`** - Scripts for model verification and attack graph generation
- **`./relaxedAssumption/`** - Models with relaxed assumptions and their verification results
- **`./BLE_SC_Asso_Model_Selection.txt`** - FVP verification results for association model selection logic

## Prerequisites

### Docker Image Setup

1. Download the Docker image `tamarin-container_1.8.0.tar` from:
   - **Download Link**: https://app.filen.io/#/d/004b7e20-bfcc-4cc7-b00d-be6a83c491bd#Hw5mfgqslPmVweIhCtyWWUtzCEkgd6Ft

2. Copy the downloaded file to `./ExpRun/files/`

### Server Configuration

Configure your server infrastructure in `./ExpRun/servers.json`:

```json
[
    {
        "host": "Server IP",
        "port": 22,
        "username": "Your Username",
        "password": "Your Password",
        "workdir": "Absolute Path to Working Directory (/tmp/xxx/ble_exp)",
        "workers": 4, // Number of docker containers on this server. Delete this comment
        "weight": 1 // Unused but do not delete it. Delete this comment
    }
]
```

**Note**: The specified users must have permissions to create and manage Docker containers.

## Model Verification

The verification process requires **Ubuntu 24.04** and involves the following steps:

```bash
# Install dependencies
apt install make m4 python3-venv

# Set up Python environment
python3 -m venv .myvenv
source .myvenv/bin/activate
pip3 install -r requirements.txt

# Run verification (this will take several weeks)
make all
```

The verification process will:
- Automatically verify 84 models across all pairing cases
- Generate attack graphs upon completion
- Utilize 20 Docker containers distributed across 6 servers
- **Estimated completion time**: ~5 days with the specified infrastructure

## Results

### Verification Results
**Download**: https://app.filen.io/#/d/acaf1c69-a587-4b18-9b3b-1eea87dfdbc1#Kby607qruJelRAGP1fsfErf1NZDmS46W

### Attack Graphs
**Download**: https://app.filen.io/#/d/c1be86c4-2540-44e3-ba5c-0e662c223dd1#28Y2GqSbuZWc7exubjmpWSyDzSUvyZel

## Attack Implementation

### Controlled Attack Environment

![Controlled Attack Environment](./Attack/controlled-attack-environment.png)

The `./Attack` directory contains:

- Custom firmware for nRF-52840 dongles
- `ble_lancet` - Man-in-the-Middle attack tool
- Proof-of-Concept implementations
- Required Python libraries

### Attack Setup

1. Configure the nRF-52840 dongle as the Bluetooth controller for BlueZ on Ubuntu
2. Use BlueZ as the Bluetooth client
3. Initiate BLE-SC pairing sessions between two devices

### Attack Scenarios

**Case 1 - Static Passkey**:
- User enters `123456` as passkey on both devices

**Case 2 - Passkey Reuse**:
- User enters random passkey in first pairing session
- Reuses the same passkey in second pairing session

## Notes

- The formal verification process is computationally intensive and requires significant time and resources
- All file hosting links are anonymous and secure
- Ensure proper Bluetooth controller configuration before running attack scenarios