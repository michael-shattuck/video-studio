#!/bin/bash
set -e

RESOURCE_GROUP="video-studio-rg"
VM_NAME="fish-speech-vm"
LOCATION="eastus"
VM_SIZE="Standard_NC4as_T4_v3"
ADMIN_USER="azureuser"

echo "=== Deploying Fish Speech to Azure ==="
echo "VM Size: $VM_SIZE (T4 GPU, 16GB VRAM)"
echo "Estimated cost: ~\$0.53/hour"
echo ""

read -p "Create Azure VM? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo "[1/5] Creating resource group..."
az group create --name $RESOURCE_GROUP --location $LOCATION 2>/dev/null || true

echo "[2/5] Creating VM with T4 GPU..."
az vm create \
    --resource-group $RESOURCE_GROUP \
    --name $VM_NAME \
    --image "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest" \
    --size $VM_SIZE \
    --admin-username $ADMIN_USER \
    --generate-ssh-keys \
    --public-ip-sku Standard \
    --priority Spot \
    --eviction-policy Deallocate \
    --max-price 0.20

VM_IP=$(az vm show -d -g $RESOURCE_GROUP -n $VM_NAME --query publicIps -o tsv)
echo "VM IP: $VM_IP"

echo "[3/5] Opening port 8080..."
az vm open-port --resource-group $RESOURCE_GROUP --name $VM_NAME --port 8080 --priority 1010

echo "[4/5] Installing Fish Speech on VM..."
ssh -o StrictHostKeyChecking=no $ADMIN_USER@$VM_IP 'bash -s' << 'REMOTE_SCRIPT'
set -e

# Install NVIDIA drivers
sudo apt-get update
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall

# Install CUDA toolkit
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get install -y cuda-toolkit-12-4

# Install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda
eval "$($HOME/miniconda/bin/conda shell.bash hook)"
conda init

# Clone and setup Fish Speech
git clone https://github.com/fishaudio/fish-speech ~/fish-speech
cd ~/fish-speech
conda create -n fish-speech python=3.10 -y
conda activate fish-speech
pip install -e .
pip install huggingface_hub

# Download model
mkdir -p checkpoints
huggingface-cli download fishaudio/openaudio-s1-mini --local-dir checkpoints/openaudio-s1-mini

# Create systemd service
sudo tee /etc/systemd/system/fish-speech.service << 'EOF'
[Unit]
Description=Fish Speech TTS Server
After=network.target

[Service]
Type=simple
User=azureuser
WorkingDirectory=/home/azureuser/fish-speech
Environment="PATH=/home/azureuser/miniconda/envs/fish-speech/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/azureuser/miniconda/envs/fish-speech/bin/python -m tools.api_server \
    --listen 0.0.0.0:8080 \
    --llama-checkpoint-path checkpoints/openaudio-s1-mini \
    --decoder-checkpoint-path checkpoints/openaudio-s1-mini/codec.pth \
    --decoder-config-name modded_dac_vq \
    --compile
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable fish-speech

echo "Fish Speech installed. Rebooting to load NVIDIA drivers..."
REMOTE_SCRIPT

echo "[5/5] Rebooting VM to load GPU drivers..."
az vm restart --resource-group $RESOURCE_GROUP --name $VM_NAME

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "VM IP: $VM_IP"
echo "Fish Speech API: http://$VM_IP:8080"
echo "Docs: http://$VM_IP:8080/docs"
echo ""
echo "After reboot (~2 min), start the service:"
echo "  ssh $ADMIN_USER@$VM_IP 'sudo systemctl start fish-speech'"
echo ""
echo "Check logs:"
echo "  ssh $ADMIN_USER@$VM_IP 'sudo journalctl -u fish-speech -f'"
echo ""
echo "Add to your .env:"
echo "  FISH_SPEECH_URL=http://$VM_IP:8080"
