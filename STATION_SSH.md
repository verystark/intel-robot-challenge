# SSH into the station laptop

Lets the dev machine running Claude Code reach the Intel station laptop, to install Studio, check
devices and run scripts remotely. Calibration and teleop stay with whoever is at the station, and
nothing that moves the arm runs without someone there confirming it's clear.

Run everything below **on the Intel laptop** (terminal: Ctrl+Alt+T).

## 1. Install and start the SSH server

```bash
sudo apt-get update
sudo apt-get install -y openssh-server
sudo systemctl enable --now ssh
systemctl status ssh --no-pager | head -3     # should say "active (running)"
```

## 2. Authorize the dev machine's key

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIurQ6APReXUDS3PYnDDSJ1cfbk19RFfm/UZ8AcnPGdi claude-dev' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

## 3. Firewall (only if active)

```bash
sudo ufw status            # if it says "active":
sudo ufw allow ssh
```

## 4. Privileged setup to do yourself

Sudo can't be typed in over SSH, so run these once while you're at the laptop:

```bash
sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker,dialout,video,render,plugdev $USER
```

Then **log out and back in** (group changes only apply to new logins). Everything after this works
without sudo.

## 5. Send back the connection details

```bash
whoami
hostname -I                # first address, e.g. 192.168.x.x or 10.x.x.x
```

## If the connection times out

Venue Wi-Fi often blocks devices from reaching each other. Fixes, simplest first:

1. Put both machines on the same phone hotspot.
2. Tailscale: on the Intel laptop run
   `curl -fsSL https://tailscale.com/install.sh | sh` then `sudo tailscale up`. On the dev machine,
   install Tailscale on Windows (WSL reaches the tailnet through Windows) and log in to the same
   account. Then use the laptop's `100.x.x.x` address from `tailscale ip -4`.

## Optional: key-only logins

Shared venue network, so once key login works, turn off password logins:

```bash
echo 'PasswordAuthentication no' | sudo tee /etc/ssh/sshd_config.d/10-keys-only.conf
sudo systemctl restart ssh
```

## Before returning the laptop

```bash
sed -i '/claude-dev$/d' ~/.ssh/authorized_keys
sudo rm -f /etc/ssh/sshd_config.d/10-keys-only.conf
sudo apt-get remove -y openssh-server
```
