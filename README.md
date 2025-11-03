# BLE Secure Connections Pairing Formal Verification (AE Version)

This repository contains the formal models, verification scripts, and attack implementations for analyzing the security of BLE Secure Connections pairing protocols.

**Note: This is an AE (Artifact Evaluation) version with reduced experimental scale for feasible reproduction.**

## 📁 Repository Structure

- **`./Attack/`** - Firmware and tools for implementing PE confusion attacks
- **`./ExpCode/`** - Scripts for Tamarin prover formal models generation
- **`./ExpRun/`** - Scripts for model verification and attack graph generation
- **`./ExpSubset/`** - A reduced subset of formal models for AE reproduction
- **`./relaxedAssumption/`** - Models with relaxed assumptions and their verification results
- **`./BLE_SC_Asso_Model_Selection.txt`** - FVP verification results for association model selection logic

## 💻 System Requirements

- **Hardware**: AMD64 architecture, 8 CPU cores, 16GB RAM
- **OS**: Ubuntu 24.04 LTS
- **Storage**: 128GB available space

## ⚙️ Prerequisites Setup

### 1. Install Dependencies

```bash
# Update system and install required packages
sudo apt update
sudo apt install -y docker.io openssh-server make m4 python3-venv curl

# Add user to docker group (requires re-login)
sudo usermod -aG docker $USER
```

**Notes**: Make sure SSH and Docker services are running properly. User must have permissions to run Docker commands without `sudo`.

### 2. Set Up Python Environment

```bash
# Create and activate Python virtual environment
python3 -m venv .myvenv
source .myvenv/bin/activate
pip3 install -r requirements.txt
```

### 3. Download Docker Image and Required Files

```bash
# Download Tamarin Prover Docker image
curl -L -o ./ExpRun/files/tamarin-container_1.8.0.tar \
  "https://github.com/itachiMin/BLE-Model-Results-PoC/releases/download/v1.0.0/tamarin-container_1.8.0.tar"
```

`ExpRun/files` directory shall contain the following files:

```
./ExpRun/files/
├── hardware.py
├── run_tamarin.sh
├── tamarin-container_1.8.0.tar
└── verify.py
```


### 4. Configure Server Settings

Edit `./ExpRun/servers.json` to use local machine only:

```json
[
    {
        "host": "127.0.0.1",
        "port": 22,
        "username": "your_username",
        "password": "your_password", 
        "workdir": "/tmp/ble_exp_ae",
        "workers": 1,
        "weight": 1
    }
]
```

**Note**: Replace `your_username` and `your_password` with your actual system credentials.

## Model Verification (AE Scale)

The verification process uses a reduced subset of models for feasible AE reproduction:

```bash
# Activate Python virtual environment
source .myvenv/bin/activate
# Run verification with reduced subset (estimated time: about 10 hours)
make subset
```

The AE verification process will:
- Automatically verify 16 representative models from the full set of 84 models
- **Estimated completion time**: about 10 hours on specified hardware
- **Full verification**: Run `make all` to execute the complete 84-model verification (estimated to take about 8 weeks on a single machine)

## 📊 Results

After verification is completed, the results will be saved in the `./ExpRun/results/` directory.
This directory stores verification results for all models, with each case corresponding to a subdirectory containing the verification results for each lemma of that model.

Use the following commands to view the results:

```bash
# View results for a specific case, for example: BLE-SC_I[NoInputNoOutput_NoOOB_NoAuthReq_KeyHigh]_R[NoInputNoOutput_NoOOB_NoAuthReq_KeyHigh]
cd ./ExpRun/results/BLE-SC_I[NoInputNoOutput_NoOOB_NoAuthReq_KeyHigh]_R[NoInputNoOutput_NoOOB_NoAuthReq_KeyHigh]

# View results for all lemmas in this case
docker run --rm -it -p 3001:3001 -v $(pwd):/root ghcr.io/luojiazhishu/tamarin-docker/cli:latest tamarin-prover interactive --interface=0.0.0.0 --derivcheck-timeout=0 .

# Open http://localhost:3001 in your browser to view the results
```

**Note**: Due to limitations of the tamarin-prover web interface, only 5 files are displayed. If you need to view results for all lemmas, place each lemma in a separate directory and view them sequentially.
Alternatively, use the `crawler.py` script to capture images of all violated lemmas (this is automatically executed in the full verification):

```bash
source .myvenv/bin/activate
cd ./ExpRun
python3 crawler.py
```

### Verification Results
Complete verification results are available at the following link:
[https://app.filen.io/#/d/acaf1c69-a587-4b18-9b3b-1eea87dfdbc1#Kby607qruJelRAGP1fsfErf1NZDmS46W](https://app.filen.io/#/d/acaf1c69-a587-4b18-9b3b-1eea87dfdbc1#Kby607qruJelRAGP1fsfErf1NZDmS46W)

### Attack Graphs
Complete attack graphs are available at the following link:
[https://app.filen.io/#/d/c1be86c4-2540-44e3-ba5c-0e662c223dd1#28Y2GqSbuZWc7exubjmpWSyDzSUvyZel](https://app.filen.io/#/d/c1be86c4-2540-44e3-ba5c-0e662c223dd1#28Y2GqSbuZWc7exubjmpWSyDzSUvyZel)


## 📝 Notes for AE Reproduction

- This AE version uses a carefully selected subset of verification cases to demonstrate the key findings while reducing computational requirements
- The full verification with 84 models requires ~5 days with distributed infrastructure, while the AE subset completes in 10 on a single machine
- Ensure Docker is properly installed and your user has permissions to run Docker commands
- SSH server configuration is required for the distributed verification framework, even when running locally