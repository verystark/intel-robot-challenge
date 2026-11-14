# Connecting to the station laptop over SSH

The station laptop is the SSH host. Setup is in [STATION_SSH.md](STATION_SSH.md); this page covers
connecting to it from another machine.

## Host status (checked 2026-11-14)

Nothing more needs doing on the station laptop:

- **Server:** `openssh-server` running on port 22, starts at boot. Key logins only; password
  logins are off (`/etc/ssh/sshd_config.d/10-keys-only.conf`).
- **Address:** `192.168.202.126` on Wi-Fi `Hype-Guest` (DHCP, may change: re-check on the laptop
  with `hostname -I`).
- **Allowed key:** only `claude-dev`. Only a machine holding that key's private half can log in.
- **Host key:** `SHA256:LKijvmj3UbLt7EH9TQ705lHQyckMYD355ZCAXvq+JUc` (ED25519).

`Hype-Guest` does let devices reach each other: a machine at `192.168.202.151` reached sshd at
06:26, then disconnected before logging in. That most likely means it didn't offer the
`claude-dev` key.

## Connect from the machine with the `claude-dev` key

```bash
ssh intel@192.168.202.126
```

If `claude-dev` isn't that machine's default key, name it:

```bash
ssh -i ~/.ssh/<that key file> intel@192.168.202.126
```

On the first connection, type `yes` only if the fingerprint matches the host key above. On shared
venue Wi-Fi, a different fingerprint means you are not talking to our laptop.

## Connect from a different machine

`ssh-copy-id` won't work because password logins are off. Instead:

1. On the machine you want to connect from:

   ```bash
   cat ~/.ssh/id_ed25519.pub        # if missing, run: ssh-keygen -t ed25519
   ```

2. Send that one line to whoever is at the station laptop. On the station laptop they run:

   ```bash
   echo '<the pasted line>' >> ~/.ssh/authorized_keys
   ```

3. Connect with `ssh intel@192.168.202.126` as above.

Add any extra keys to the cleanup in
[STATION_SSH.md](STATION_SSH.md#before-returning-the-laptop) so they are removed before the laptop
goes back.

## If it still fails

On the connecting machine:

```bash
ssh -v intel@192.168.202.126
```

- **Timeout:** network problem. Re-check the laptop's address, or see
  [If the connection times out](STATION_SSH.md#if-the-connection-times-out).
- **`Permission denied (publickey)`:** the wrong key was offered. Use `-i` with the right key, or
  add this machine's key as above.
