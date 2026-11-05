# Self-Hosting a Streamlit App with Docker, GitHub, and Kubernetes

This guide assumes you already have a working Streamlit application in a repository. It walks you through containerizing it, storing it on GitHub, and deploying it automatically to Kubernetes, with a strong focus on **host and network hardening**. It is written for **running the stack on the same Linux machine you use as a NAS**; **§1.4** documents **residual risk** you cannot fully “YAML away,” and **§2** states your operational plan and terms. **§1.5** is addressed to **any AI** that helps you implement this stack.

**How to read the tags**

- **(Human)** — Requires judgment, money, legal consent, physical access, or credentials you should not paste into chat tools. You perform these steps yourself (optionally with an assistant drafting files *locally* after you review them).
- **(AI)** — Suitable to automate or draft with an AI coding agent: commands, manifests, workflow YAML, Dockerfile edits, and repetitive refactors—**after** you understand what each artifact does. Always review AI output before applying it to production systems.

---

## Table of contents

1. [Goals, scope, and safety first](#1-goals-scope-and-safety-first) — **§1.4** residual risk (NAS + app); **§1.5** AI duty to flag risky patterns
2. [Your plan: one machine for NAS and Streamlit](#2-your-plan-one-machine-for-nas-and-streamlit) — rules of thumb; terms table
3. [What you will install and in what order](#3-what-you-will-install-and-in-what-order)
4. [Phase A — Dockerize your Streamlit app](#phase-a--dockerize-your-streamlit-app)
5. [Phase B — GitHub: repository, branches, and secrets](#phase-b--github-repository-branches-and-secrets)
6. [Phase C — Your Kubernetes host (NAS / app machine)](#phase-c--your-kubernetes-host-nas--app-machine)
7. [Phase D — Baseline Kubernetes cluster (example: k3s on your Linux host)](#phase-d--baseline-kubernetes-cluster-example-k3s-on-your-linux-host)
8. [Phase E — Container registry and pulling private images](#phase-e--container-registry-and-pulling-private-images)
9. [Phase F — Kubernetes objects for Streamlit](#phase-f--kubernetes-objects-for-streamlit)
10. [Phase G — TLS, domain, and Ingress](#phase-g--tls-domain-and-ingress)
11. [Phase H — Automatic deployment from GitHub](#phase-h--automatic-deployment-from-github)
12. [Phase I — Security hardening checklist](#phase-i--security-hardening-checklist)
13. [Operations: updates, rollbacks, logs, backups](#operations-updates-rollbacks-logs-backups)
14. [Troubleshooting](#troubleshooting)
15. [Glossary](#glossary)

---

## 1. Goals, scope, and safety first

### 1.1 What “self-hosted” means here **(Human)**

You will run **your own** deployment pipeline and **your own** Kubernetes environment on a **Linux machine you control**—in your case, the **same** host that acts as your NAS (**§2**). You are responsible for patches, backups, and incident response.

### 1.2 The main risk you asked to avoid **(Human)**

If you expose a service from a machine that also holds family photos, tax documents, or other irreplaceable files, a flaw in the **app**, **dependencies**, **container stack**, **ingress/proxy**, or the **OS kernel** can become a path to reading or destroying **that same machine’s data**. “Professional” deployment reduces **how likely** that is and **how far** an attacker can get, but it cannot honestly promise **zero** risk while the sensitive data and the internet-facing stack share one physical system and one kernel.

**Layers that always help (whether or not you colocate NAS and app):**

- **Do not** rely on ad hoc port forwarding without a firewall story, TLS, patching discipline, and least privilege.
- **Do** use **TLS** (HTTPS), **least privilege**, **secrets handling** (no secrets baked into images), **host and router firewalls**, **automatic security updates**, and **tested backups** you have actually restored from.
- **Ideal separation (only pattern that removes colocation risk):** run the public app on a **different** machine (for example a small VPS) from the system that stores precious NAS data, so a compromise of the app host does not trivially inherit local access to your ZFS pool or SMB shares.

**If you deliberately run Streamlit on the same Linux box that is your NAS** (your stated plan), treat the rest of this guide as **defense in depth on a high-stakes host**—not equivalent to physical isolation. Read **§1.4** before you expose anything to the internet.

### 1.3 What this guide does *not* cover in depth **(Human)**

- Legal/compliance (GDPR, HIPAA, etc.) if your app processes regulated data.
- Full SOC2-style security program—this is a strong baseline for a personal or small-team app.

### 1.4 Same machine as NAS *and* public app: what you can fix, what you cannot **(Human)**

This section exists because you intend one Linux host to **both** serve NAS workloads (for example Samba/NFS, sync tools, backup targets) **and** run containers exposed (directly or indirectly) to the internet. That is a common home setup and it can be operated **seriously**, but you should understand **residual risk** in plain terms.

#### 1.4.1 Why risk cannot be “resolved to zero” on one colocated host **(Human)**

A NAS + Kubernetes + ingress + Streamlit stack shares:

| Shared asset | Why it matters |
|--------------|----------------|
| **One kernel** | Any **kernel** vulnerability (local privilege escalation, remote entry if exposed) can affect **every** process and filesystem the kernel can reach, including your NAS datasets. Containers are **not** magic security boundaries; they are **isolation hints** enforced by that same kernel. |
| **One set of physical disks** | Ransomware-style destruction, accidental `rm -rf`, or a bug in a backup script run as a privileged user can harm NAS data **without** “hacking” Streamlit at all. |
| **One admin surface** | SSH, web UIs for NAS software, Kubernetes API, and third-party agents are all **extra doors**. Misconfiguration (password reuse, world-readable shares, overly broad `sudo`) compounds internet-facing risk. |
| **Supply chain** | Your app’s Python dependencies, container base images, Helm charts, and CI tokens are all **trust anchors**. Professional practice reduces exposure; it does not **prove** absence of malicious or vulnerable code. |

**Bottom line:** No combination of Docker hardening, NetworkPolicies, TLS, and GitOps can mathematically guarantee that a determined attacker—or a subtle bug—will never reach NAS files on **the same machine**, because those controls sit **above** the kernel and **beside** misconfiguration and insider-style mistakes. **The only architectural way to remove that class of colocation risk** is to **not** store irreplaceable data on the same host that terminates untrusted HTTP from the internet (use a separate VPS or a second small PC for the app tier).

That is not fatalism: it is the honest tradeoff. If you still colocate, the goal is to make breaches **harder, slower, and more detectable**, and to ensure **backups** survive even a serious incident.

#### 1.4.2 What “as professional as possible” *does* buy you on a NAS box **(Human)**

These practices **do** materially improve safety **even on one host**:

- **Network:** Default-deny host firewall; only **80/443** (and tightly scoped admin paths) from the internet; **no** SMB/NFS ports forwarded from your router to this machine unless you truly need remote file access—and then prefer **VPN** (WireGuard, Tailscale) instead of exposing file protocols publicly.
- **Identity:** Separate Linux accounts for NAS services vs cluster admin; **SSH keys**; disable password SSH; **2FA** on any cloud/GitHub accounts that can push images or deploy.
- **Containers:** Non-root workloads, **read-only root filesystem** where Streamlit allows it, **drop Linux capabilities**, **seccomp** defaults, **resource limits**, **no hostPath mounts** from NAS directories unless strictly required—and if required, **read-only** and minimal subtree.
- **Data layout:** Store precious data on datasets/volumes with **ZFS/btrfs snapshots** (or equivalent), **strict POSIX ACLs**, and **encryption at rest** where supported; never mount the entire NAS into a pod “for convenience.”
- **Secrets:** Kubernetes Secrets or a proper secret operator; **rotate** deploy credentials; never commit kubeconfig or PATs to git (including AI-generated snippets in issues).
- **Observability:** Central or local logs for ingress and auth failures; alerts on disk anomalies; periodic **restore tests** from backups.
- **Process:** Small, reviewed changes; protected `main`; image tags pinned by digest for reproducible rollbacks.

#### 1.4.3 Residual risks that remain even if you do everything above **(Human)**

- **Kernel or hypervisor zero-days** affecting your distribution.
- **Logic bugs** in your own app that leak data or allow abuse without “breaking out” of the container.
- **Human error**: a one-line `kubectl` or `chmod` that opens a share or API too widely.
- **Physical theft** or seizure of the machine (mitigated by full-disk encryption and strong account passwords, not eliminated for a powered-on server).

If any of those are unacceptable, the mitigation is **organizational / architectural** (separate hardware or cloud for the app; keep NAS off the public attack path), not more YAML alone.

### 1.5 Duty for any AI assisting with this deployment **(AI)**

This subsection is **normative for assistants**: if you are an AI (coding agent, chat model, or similar) and you are helping the user design, edit, or run anything related to this guide—Dockerfiles, Compose files, Kubernetes manifests, CI workflows, firewall rules, NAS integration, or operational commands—you **must** treat **host and NAS safety** as a first-class requirement.

**What you must do**

- When you notice a **pattern, suggestion, or artifact** (whether from the user, from prior chat context, or from your own draft) that **increases risk** compared to the baseline in **§1.2–§1.4** and the hardening themes elsewhere in this guide, you **must notify the user explicitly** before or as you proceed. Do not silently implement high-risk choices just because the user asked once.
- Your notification **must include justification** using **technical and logical reasoning**: name the mechanism (for example: expanded attack surface, privilege boundary crossed, confidentiality/integrity impact on colocated NAS data, persistence or lateral movement), cite the relevant construct (ports, mount types, identity, network path, secret handling), and state **why** severity is higher **in this architecture** (single host, internet exposure, etc.).

**Examples of patterns that typically warrant a warning** (non-exhaustive; use judgment):

- Exposing **file-server or management** ports to the internet (`445`, `2049`, `111`, `139`, NAS vendor UI ports, Kubernetes **`6443`** wide open, SSH with passwords) instead of VPN-scoped or IP-restricted access.
- **`hostPath`** or bind mounts from **NAS or home directories** into pods, especially **read-write**, or running the container as **root** on a NAS host.
- **Secrets** in images, git, workflow logs, or chat pastes; overly powerful **`KUBE_CONFIG`** or PATs in CI without rotation or scoping.
- **Disabling TLS**, weak ingress defaults, **`privileged: true`**, **`CAP_SYS_ADMIN`**, turning off **seccomp** / AppArmor where the guide assumes hardening.
- **`NetworkPolicy` absent or “allow all”** when the user’s goal is strict containment on a colocated NAS.
- CI that **auto-deploys** from unreviewed branches or untrusted forks without equivalent controls.

**What this is not**

- It is **not** a guarantee that you will catch every vulnerability; it is a **duty to speak up** when recognized dangerous patterns appear, with clear reasoning.
- It does **not** replace **human** review, penetration testing, or the user’s responsibility for backups and legal compliance.

**For the human user:** If an AI ignores **§1.5**, treat that as a red flag about the session; re-prompt with “apply **§1.5**: review this plan for elevated risk and justify any concerns.”

---

## 2. Your plan: one machine for NAS and Streamlit **(Human)**

**Context:** **§1.2** and **§1.4** already explain that keeping irreplaceable NAS data on a **different** host from the internet-facing app is the lowest **architectural** risk. You are **choosing to colocate** NAS services and your Streamlit / Kubernetes stack on **one Linux machine** (no extra hosting bill for a separate server), and you accept the **residual risk** there while still applying as much hardening as the guide describes.

**What the rest of this document assumes:** Phases **C** through **I** target Kubernetes running on **that same host**—not on a rented VM elsewhere.

### Operational rules for this layout **(Human)**

1. **Internet exposure:** Allow only **HTTP(S)** (**80** / **443**) from the internet to this host (router **port forwarding** to its **LAN** IP, or a tunnel product if you use one). **Never** expose SMB (**445**), NFS (**2049**), iSCSI, or NAS vendor admin UIs to the public internet; use a **VPN** for remote file access.
2. **LAN exposure:** Keep NAS shares **authenticated**; disable guest access; use **strong, unique** passwords or certificates per client; put IoT on a **VLAN** if your router supports it so untrusted devices cannot freely reach this host.
3. **Container ↔ disk boundary:** Do not mount whole NAS trees into Streamlit pods. If the app needs data, mount **only** the required path, **read-only** unless writes are strictly necessary, with a **dedicated** UID/GID and dropped capabilities.
4. **Admin access:** Prefer **Tailscale** / **WireGuard** for **SSH** and the Kubernetes API (**6443**) from outside the home instead of leaving those ports open to the whole internet.
5. **Backups:** Assume **ransomware or wipe** is possible; keep **offline or off-site** backups an attacker on this machine cannot destroy in one step.

Docker, GitHub Actions, k3s, Ingress, cert-manager, and the hardening checklist still apply; the **risk story** is entirely **§1.4** (one kernel, one pool of disks).

### Terms you will see later **(Human)**

| Term | Meaning |
|------|---------|
| **IP** | **Internet protocol address** — identifies a host. Your router has a **public** IP (what the internet sees). Your NAS/app machine has a **LAN** IP (for example `192.168.1.x`) on your home network. |
| **DNS** | **Domain name system** — maps `app.example.com` to an IP. For home hosting you usually set an **A** record to your router’s **public** IP and **forward** **80** and **443** to this machine’s **LAN** IP (Let’s Encrypt **HTTP-01** needs **80** reachable from the internet). **CGNAT** or an ISP blocking inbound **80**/**443** breaks that pattern unless you use **DNS-01** validation, a tunnel, or another workaround—research separately if you hit that wall. |
| **HTTP** / **HTTPS** | Web traffic; **HTTPS** uses **TLS** so browsers encrypt the session to your ingress. |
| **TLS** | **Transport layer security** — the encryption used by HTTPS; often terminated at the **ingress controller** on this host. |
| **SSH** | Encrypted remote shell—commonly port **22**; prefer keys over passwords. |
| **NAT** | Your router maps many LAN devices to one public IP; **port forwarding** sends chosen inbound ports to your NAS host’s LAN IP. |
| **VPN** | e.g. **WireGuard**, **Tailscale** — reach admin services without exposing them globally. |
| **SMB** / **NFS** | File-sharing protocols for the **LAN**; do not publish them to the internet. |
| **Kubernetes** | Runs your app in **pods**; connects them via **services** and **ingress**. |
| **Ingress** / **ingress controller** | Routes `https://your-hostname/…` to the correct **service** inside the cluster; often obtains TLS certificates. |
| **Service** / **Pod** | In-cluster networking and the running Streamlit **container(s)**. |

**Optional later:** A **VPS** (*virtual private server*) is a small Linux VM you **rent** from a hosting company. **§1** still mentions it as the separation option if you ever split the app tier off this machine; the step-by-step phases below **do not** assume you use one.

---

## 3. What you will install and in what order

| Order | Component | Role |
|------|-----------|------|
| 1 | Docker (local) | Build/test the image on your dev machine |
| 2 | GitHub repo | Source of truth + CI triggers |
| 3 | Your Linux NAS host + k3s (example) | Lightweight Kubernetes on the same machine |
| 4 | Ingress + cert-manager | HTTPS and routing by hostname |
| 5 | GitHub Actions | Build/push image; deploy manifests |
| 6 | Registry (e.g., GHCR) | Stores images the cluster pulls |

---

## Phase A — Dockerize your Streamlit app

### A.1 Install Docker Desktop (Windows) **(Human)**

**What you do**

1. Open a browser and go to: `https://www.docker.com/products/docker-desktop/`
2. Download **Docker Desktop for Windows**.
3. Run the installer. When prompted:
   - Enable **WSL 2** backend if offered (recommended on Windows 10/11).
4. After installation, open **Docker Desktop** from the Start menu.
5. Wait until the whale icon in the system tray shows **“Docker Desktop is running”**.

**What this does:** Installs the Docker engine and tools so you can build container images locally.

**How it does it:** Docker packages your app and dependencies into an image that runs the same way on your laptop, your Linux host, and Kubernetes.

### A.2 Verify Docker **(Human)**

Open **PowerShell** (Start → type `PowerShell` → open **Windows PowerShell**).

```powershell
docker version
```

**Expected:** Client and Server sections both print version info.

**What this does:** Confirms the Docker daemon is running.

### A.3 Create a `Dockerfile` at the repo root **(AI)** — *you review*

**What to name it:** Save the file as exactly **`Dockerfile`** (capital **D**, no `.txt` or other suffix) in your **repository root**—the same directory as `requirements.txt` and the one you `cd` into before `docker build`. Docker uses that filename by default; you only need `docker build -f …` if you put the instructions elsewhere.

**What this does:** Defines how to build a runnable image: base OS layer, install dependencies, copy code, set command.

**How it does it:** Each `Dockerfile` instruction creates a layer; Kubernetes will start containers from the final image.

Example pattern (adjust paths and filenames to match **your** app):

```dockerfile
# Base image: official Python on Debian Bookworm "slim" (smaller footprint than the non-slim image).
# Pin 3.12.x here so automated rebuilds do not jump to a new Python minor without you noticing.
FROM python:3.12-slim-bookworm

# Environment variables seen by every RUN/CMD layer and by your Python process:
# PYTHONDONTWRITEBYTECODE=1 — do not write .pyc files into the image (fewer writes, slightly smaller tree).
# PYTHONUNBUFFERED=1 — stdout/stderr are not fully block-buffered; logs appear quickly in `docker logs` / Kubernetes logs.
# PIP_NO_CACHE_DIR=1 — pip does not retain a wheel cache inside the layer (smaller final image).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Working directory inside the image; created if missing. Later COPY/RUN paths are relative to here unless absolute.
WORKDIR /app

# OS-level compilers/headers for Python packages that build native extensions during pip install.
# --no-install-recommends avoids pulling in weak "recommended" packages; deleting /var/lib/apt/lists/* trims layer size.
# Remove this RUN entirely if your requirements install as pure wheels and never need a compiler.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency manifest first: Docker caches this layer until requirements.txt changes, so editing
# application code does not always force a full reinstall of all Python packages on rebuild.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the project into /app (honors .dockerignore — keep secrets and bulky dirs out of the build context).
COPY . .

# Create a dedicated non-root account and give it ownership of the app tree (needed if Streamlit or deps write under /app).
# USER 10001 uses a numeric UID so Kubernetes `runAsNonRoot` and cross-image portability do not depend on passwd name lookups.
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER 10001

# Documents the container's listening port for humans and for `docker run -P`; it does not publish the port by itself.
EXPOSE 8501

# CMD uses JSON "exec" form: streamlit is PID 1 without a shell wrapper, so SIGTERM from `docker stop` / kubelet reaches it cleanly.
# Replace trendline_streamlit.py with your entry script (path relative to WORKDIR unless you use an absolute path).
# --server.port — Streamlit HTTP port inside the container (match EXPOSE and your Service targetPort in Kubernetes).
# --server.address=0.0.0.0 — listen on all interfaces so traffic from `docker run -p` or in-cluster networking can reach the app.
# --server.headless=true — server/container mode (avoids assumptions that a local desktop browser session is available).
CMD ["streamlit", "run", "trendline_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
```

**Replace** `trendline_streamlit.py` with your real entry file.

### A.4 Add a `.dockerignore` **(AI)** — *you review*

At the repo root, create `.dockerignore` to keep secrets and junk out of the image:

```
.git
.github
**/__pycache__
**/*.pyc
.env
*.pem
persistent_data/
```

**What this does:** Prevents copying large or sensitive files into the build context.

**How it does it:** Docker excludes these paths from `COPY . .`, shrinking images and reducing leak risk.

### A.5 Build and run locally **(Human)**

In PowerShell, `cd` to your project root (the folder that contains the `Dockerfile`).

```powershell
cd C:\Users\you\source\YourRepo
docker build -t my-streamlit:local .
```

**What this does:** Builds an image tagged `my-streamlit:local`.

Run it:

```powershell
docker run --rm -p 8501:8501 my-streamlit:local
```

**What this does:** Maps container port 8501 to your laptop’s `localhost:8501`.

**How it does it:** Docker publishes a port binding; traffic to `http://127.0.0.1:8501` hits Streamlit inside the container.

Open a browser to `http://127.0.0.1:8501` and verify the app.

Stop: focus the terminal window and press **Ctrl+C**.

---

## Phase B — GitHub: repository, branches, and secrets

### B.1 Create a GitHub account (if needed) **(Human)**

1. Browse to `https://github.com/signup`.
2. Complete email verification.

### B.2 Create a new repository **(Human)**

1. Log in to GitHub.
2. Click your **profile picture** (top right) → **Your repositories**.
3. Click the green **New** button.
4. **Repository name:** e.g., `my-streamlit-app`.
5. Choose **Private** (recommended unless you intend open source).
6. **Do not** add a README if you already have a local repo (avoids merge complexity). If GitHub creates a README, follow GitHub’s “push an existing repository” instructions.
7. Click **Create repository**.

**What this does:** Creates the remote Git home for code and CI configuration.

### B.3 Push your local code **(Human)**

Install Git for Windows if needed: `https://git-scm.com/download/win`.

In PowerShell inside your project:

```powershell
git init
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git add .
git commit -m "Initial commit: Streamlit app and Docker"
git push -u origin main
```

**What this does:** Uploads your Dockerfile and app to GitHub.

**How it does it:** Git sends objects to GitHub over HTTPS (or SSH if you configure keys).

### B.4 Enable branch protection on `main` **(Human)**

1. On GitHub, open your repo → **Settings** → **Branches** → **Add branch protection rule**.
2. **Branch name pattern:** `main`.
3. Enable **Require a pull request before merging** (recommended for teams).
4. Save changes.

**What this does:** Reduces accidental direct pushes to production configuration.

---

## Phase C — Your Kubernetes host (NAS / app machine)

This guide assumes the cluster runs on the **same Linux system** described in **§2**—your NAS and Streamlit host—not on separate rented hardware.

### C.1 Prepare the Linux host **(Human)**

1. Install or reuse a **64-bit x86_64** Linux on the machine (examples in later phases use **Ubuntu 22.04 LTS**; adapt package commands if you use another distro).
2. Note the machine’s **LAN IP** (from the host itself or your router’s DHCP list). Set a **DHCP reservation** or **static IP** so port forwards and TLS do not silently break after a reboot.
3. For **Phase G** (DNS), identify your home’s **public IPv4** (what a “what is my IP” style page shows **from inside your home network**). You will point your domain’s **A** record at that address and **forward** **80**/**443** to this host’s LAN IP—unless your ISP uses **CGNAT** or blocks inbound web ports, in which case automatic **HTTP-01** certificate issuance may fail until you adopt a different approach (tunnel, **DNS-01** with your DNS API, business line, etc.).

**What this does:** Grounds all later SSH and `kubectl` steps in **your** hardware.

**How it does it:** You already own the compute; no cloud VM signup is required for the app host itself.

### C.2 Sizing guidance **(Human)**

Budget **CPU and RAM** for **NAS workloads + Kubernetes + Streamlit** together. A modest Streamlit app might still need **several gigabytes of RAM** headroom beyond what file serving alone uses; increase if you run heavy analytics or models.

---

## Phase D — Baseline Kubernetes cluster (example: k3s on your Linux host)

> k3s is a lightweight Kubernetes distribution suitable for a **single-node** home server. **(Human)** You are responsible for backing up any data you care about on this machine—including NAS datasets.

### D.1 Reach the Linux host and note its addresses **(Human)**

1. Ensure the NAS / app machine is on, connected to the LAN, and reachable (optional: `ping YOUR.LAN.IP` from another PC).
2. From **Windows PowerShell** on a laptop on the **same LAN** (unless you use a VPN into home):

```powershell
ssh your-linux-user@YOUR.LAN.IP.ADDRESS
```

Use a Linux account that can run `sudo` (your distro may disable **root** SSH login entirely).

3. Keep handy: the host’s **LAN IP**, and (for DNS in **Phase G**) your router’s **public** WAN address if you will port-forward **80**/**443** to this host.

**What this does:** Opens an encrypted admin shell on the machine that will run k3s.

**How it does it:** **SSH** authenticates you to **your** hardware.

### D.2 Update the OS **(Human)**

On the Linux host shell:

```bash
sudo apt-get update && sudo apt-get -y upgrade
```

**What this does:** Installs security patches.

### D.3 Install k3s (server) **(Human)** — *AI may draft a script; you run on the Linux host*

On the Linux host:

```bash
curl -sfL https://get.k3s.io | sh -
```

**What this does:** Installs Kubernetes control plane + worker components on one node.

**How it does it:** The installer downloads binaries and sets up `systemd` services.

Verify:

```bash
sudo kubectl get nodes
```

**Expected:** One node `Ready`.

### D.4 Copy kubeconfig to your laptop (optional but convenient) **(Human)**

On the Linux host, show the kubeconfig (contains **secrets**—treat carefully):

```bash
sudo cat /etc/rancher/k3s/k3s.yaml
```

**What this does:** Lets `kubectl` on your PC talk to the cluster.

**How to use safely:**

1. On your PC, save the file as `C:\Users\you\.kube\config-k3s` (create `.kube` if missing).
2. Edit the file: replace `127.0.0.1` in the `server:` URL with an address your PC can route to—usually the host’s **LAN IP** when you run `kubectl` from home, or a **Tailscale/WireGuard** IP if you use mesh VPN. **Do not** expose k3s API port **6443** on the public internet; restrict it with **host firewall** and/or **router** rules to trusted IPs or VPN only (see hardening).

Test from PowerShell (after installing `kubectl`—see next step):

```powershell
kubectl --kubeconfig $env:USERPROFILE\.kube\config-k3s get nodes
```

Install `kubectl` on Windows: follow `https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/`.

**Security note:** Prefer **not** exposing 6443 to `0.0.0.0/0`. Restrict to your home IP or use a VPN.

---

## Phase E — Container registry and pulling private images

### E.1 Use GitHub Container Registry (GHCR) **(Human)**

You will push images to `ghcr.io/<org-or-user>/<image>:<tag>`.

**What this does:** Stores versioned images GitHub Actions builds.

### E.2 Create a Personal Access Token (PAT) for CI **(Human)**

1. GitHub → your profile (top right) → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** (preferred) or **classic**.
2. For fine-grained: **Repository access** → select your repo; **Permissions** → **Contents: Read and write** (if you use GITHUB_TOKEN only, you may not need PAT for push—see Actions docs); for GHCR push with `GITHUB_TOKEN`, enable workflow permissions per GitHub’s current defaults.
3. For simplicity, many tutorials use a **classic PAT** with scopes: `write:packages`, `read:packages`, and `repo` (if private).

**What this does:** Allows automation to authenticate.

**How it does it:** HTTPS requests include the token; **never** commit tokens to git.

### E.3 GitHub Actions: build and push image **(AI)** — *you review*

Create `.github/workflows/docker-publish.yml`:

```yaml
name: Build and publish image

on:
  push:
    branches: [ "main" ]

permissions:
  contents: read
  packages: write

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

**What this does:** On every push to `main`, GitHub builds your Dockerfile and pushes tags to GHCR.

**How it does it:** Hosted runners execute Docker buildx; `GITHUB_TOKEN` authenticates to GHCR when permissions allow.

### E.4 Allow your cluster to pull private GHCR images **(Human)**

Create a Kubernetes **imagePullSecret** using a PAT that can **read** packages.

On your PC (with kubectl configured), create a secret namespace first:

```powershell
kubectl create namespace streamlit
```

Create the secret (replace values):

```powershell
kubectl create secret docker-registry ghcr-credentials `
  --namespace streamlit `
  --docker-server=ghcr.io `
  --docker-username=YOUR_GITHUB_USERNAME `
  --docker-password=YOUR_PAT_WITH_READ_PACKAGES
```

**What this does:** Stores registry credentials in the cluster encrypted at rest (etcd); pods reference this secret to pull private images.

---

## Phase F — Kubernetes objects for Streamlit

### F.1 Minimal Deployment + Service **(AI)** — *you review*

Save as `k8s/deployment.yaml` (example):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: streamlit-app
  namespace: streamlit
spec:
  replicas: 1
  selector:
    matchLabels:
      app: streamlit-app
  template:
    metadata:
      labels:
        app: streamlit-app
    spec:
      imagePullSecrets:
        - name: ghcr-credentials
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: streamlit
          image: ghcr.io/your-user/your-repo:main
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8501
          readinessProbe:
            tcpSocket:
              port: 8501
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1"
              memory: "2Gi"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: false
            capabilities:
              drop: ["ALL"]
---
apiVersion: v1
kind: Service
metadata:
  name: streamlit-app
  namespace: streamlit
spec:
  selector:
    app: streamlit-app
  ports:
    - name: http
      port: 80
      targetPort: 8501
```

**What this does:**

- **Deployment** keeps your app running; if the process crashes, Kubernetes restarts it.
- **Service** provides stable cluster DNS `streamlit-app.streamlit.svc.cluster.local` on port 80 to pods on 8501.

Apply:

```powershell
kubectl apply -f k8s/deployment.yaml
kubectl -n streamlit get pods
```

**Expected:** Pod `Running`.

---

## Phase G — TLS, domain, and Ingress

### G.1 Buy a domain **(Human)**

Use any registrar (Namecheap, Google Domains successor, Cloudflare Registrar, etc.). Purchase `example.com`.

**What this does:** Gives you a stable name instead of typing an IP.

### G.2 Point DNS at your home and forward web ports **(Human)**

In your DNS provider’s dashboard:

1. Create an **A** record: `app` → **your home’s public IPv4** (the WAN address you noted in **Phase C**; this yields `app.example.com`).
2. Optionally create an **A** record: `@` → the same public IP for the apex domain.

On your **router**, create **port forwards** (names vary): TCP **80** and **443** from the internet → **LAN IP of your NAS / app host** (same machine running k3s and ingress). Let’s Encrypt **HTTP-01** validation needs **80** reachable from the public internet during certificate issuance.

TTL: 300 seconds is reasonable while testing.

**What this does:** Sends visitors to your router’s public IP; the router sends web traffic to the Linux host running ingress.

**How it does it:** DNS publishes a name; **NAT + port forwarding** delivers the connection to the correct machine on your LAN.

**If this fails:** **CGNAT**, ISP inbound blocks, or dynamic IPs that change often require different tactics (dynamic DNS, **DNS-01** challenges, tunnels, or asking your ISP for a static or business-grade line)—treat those as follow-on research.

### G.3 Install Traefik or NGINX Ingress + cert-manager **(Human)**

k3s ships with **Traefik** ingress by default. For HTTPS, install **cert-manager** to obtain Let’s Encrypt certificates.

High-level steps on the Linux host (exact commands change over time—verify cert-manager install docs):

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/vX.Y.Z/cert-manager.yaml
```

Replace `vX.Y.Z` with the current release from `https://cert-manager.io/docs/installation/kubernetes/`.

**What this does:** Adds controllers that request and renew TLS certs automatically.

### G.4 Define ClusterIssuer (Let’s Encrypt) **(AI)** — *you review*

Example `k8s/cluster-issuer.yaml` (staging first to avoid rate limits while testing):

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: you@example.com
    privateKeySecretRef:
      name: letsencrypt-staging-account-key
    solvers:
      - http01:
          ingress:
            class: traefik
```

Apply:

```powershell
kubectl apply -f k8s/cluster-issuer.yaml
```

When everything works, duplicate for **production** issuer with `https://acme-v02.api.letsencrypt.org/directory`.

**What this does:** cert-manager proves you control the domain (HTTP-01) and stores the account key in a Kubernetes Secret.

### G.5 Ingress for your hostname **(AI)** — *you review*

Example `k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: streamlit-ingress
  namespace: streamlit
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-staging
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - app.example.com
      secretName: streamlit-tls
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: streamlit-app
                port:
                  number: 80
```

Apply:

```powershell
kubectl apply -f k8s/ingress.yaml
```

**What this does:** Routes public HTTPS traffic for `app.example.com` to your Service.

**How it does it:** The ingress controller watches Ingress objects and configures its proxy accordingly.

---

## Phase H — Automatic deployment from GitHub

You already have **automatic image builds** on push. “Auto-deploy” means: after the image is pushed, **update the cluster** to use the new tag.

### H.1 Immutable tags vs `latest` **(Human)**

**Best practice:** Deploy an **immutable digest or version tag** (for example `ghcr.io/user/repo:sha-abc1234`), not a floating `latest`, so rollbacks are exact.

### H.2 GitHub Actions deploy with kubectl **(AI)** — *you review*

Store a **kubeconfig** or (better) a **limited** service account token as a GitHub secret `KUBE_CONFIG` (base64 of kubeconfig) **only if** you accept the operational risk—rotating and scoping it tightly.

A safer pattern for beginners:

- Use **Argo CD** or **Flux** (GitOps): the cluster pulls desired state from git; CI only updates a manifest’s image tag via PR.

**Simple path (acceptable for learning):** add a job step that runs `kubectl set image ...` using a secure kubeconfig secret.

Example sketch (you must adapt to your secret handling):

```yaml
      - name: Deploy to k3s
        uses: tale/kubectl-action@v1
        with:
          base64-kube-config: ${{ secrets.KUBE_CONFIG }}
          kubectl-version: latest
      - name: Rollout new image
        run: |
          kubectl -n streamlit set image deployment/streamlit-app \
            streamlit=ghcr.io/your-user/your-repo:${{ github.sha }}
          kubectl -n streamlit rollout status deployment/streamlit-app
```

**What this does:** After build, tells Kubernetes to use the new image and waits for rollout.

**How it does it:** The API server updates the Deployment’s pod template; a rolling update replaces pods.

**Security:** The `KUBE_CONFIG` secret is powerful—**rotate** it if leaked; restrict GitHub Actions to protected branches; prefer OIDC-based cloud deployers if you move to managed Kubernetes later.

### H.3 GitOps (more professional) **(Human + AI)**

1. Install **Argo CD** on the cluster (follow official install YAML/Helm).
2. Store manifests in a repo (could be the same repo under `k8s/`).
3. Configure an Argo CD **Application** pointing at that path.
4. CI updates image tag in manifests via PR, Argo reconciles.

**What this does:** The cluster continuously converges to declared state; humans review manifest diffs.

---

## Phase I — Security hardening checklist

Each item: **what / how** briefly.

### I.1 Firewall the Linux host **(Human)**

Using `ufw` on Ubuntu:

```bash
sudo ufw default deny incoming
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

**What this does:** Blocks everything except SSH and web by default on this machine’s own interfaces.

**How it does it:** Netfilter rules on the host (`ufw` is a frontend).

### I.2 Do not expose Kubernetes API to the world **(Human)**

If your kubeconfig’s `server:` URL is reachable from the internet (for example you forwarded **6443** from the router—discouraged), restrict source IPs in the **router** and on the host with `ufw`:

```bash
sudo ufw allow from YOUR.HOME.IP to any port 6443 proto tcp
```

**What this does:** Reduces brute force / exploit surface against the API.

### I.3 SSH keys, disable password login **(Human)**

Edit `/etc/ssh/sshd_config`: set `PasswordAuthentication no`, reload SSH.

**What this does:** Prevents password guessing.

### I.4 Keep images non-root **(AI)**

Already shown in Dockerfile with `USER 10001`.

**What this does:** Limits what an RCE in the app can modify inside the container.

### I.5 NetworkPolicies (optional but strong) **(AI)**

Deny all ingress except from the ingress controller namespace; allow egress only to DNS and required APIs.

**What this does:** Contains lateral movement if a pod is compromised.

### I.6 Secrets for API keys **(Human + AI)**

Never bake secrets into the image. Use Kubernetes Secrets + restricted RBAC, or external secret operators.

```powershell
kubectl -n streamlit create secret generic app-secrets `
  --from-literal=MY_API_KEY=replace-me
```

Mount as env vars in the Deployment under `envFrom` or `env`.

**What this does:** Injects secrets at runtime.

### I.7 Resource limits **(AI)**

Already illustrated under `resources.limits`. Prevents a memory leak from taking the whole node.

### I.8 Enable automatic security updates **(Human)**

Ubuntu: `sudo apt-get install unattended-upgrades` and configure.

**What this does:** Applies critical patches without manual intervention.

### I.9 Backups **(Human)**

If your app writes persistent data, use **volume snapshots** or backup jobs—not covered here for stateless Streamlit.

---

## Operations: updates, rollbacks, logs, backups

### View logs **(Human)**

```powershell
kubectl -n streamlit logs deploy/streamlit-app --tail=200 -f
```

**What this does:** Streams stdout/stderr from containers.

### Rollback a bad deploy **(Human)**

```powershell
kubectl -n streamlit rollout undo deployment/streamlit-app
```

**What this does:** Reverts to the previous ReplicaSet.

### Update app code **(Human workflow)**

1. Edit code locally, commit to a feature branch.
2. Open PR → review → merge to `main`.
3. CI builds/pushes image and deploys (depending on your Phase H setup).

---

## Troubleshooting

| Symptom | Likely cause | What to check |
|--------|--------------|---------------|
| ImagePullBackOff | Wrong tag or pull secret | `kubectl -n streamlit describe pod PODNAME` |
| CrashLoopBackOff | Streamlit command wrong, missing file | `kubectl logs ...` |
| 404 at domain | Ingress host mismatch, DNS not propagated | `nslookup app.example.com` |
| TLS errors staging | Browser distrusts staging CA | Switch to production issuer when ready |

---

## Glossary

- **Container:** Packaged app with its filesystem slice and runtime settings.
- **Image:** Immutable template for containers.
- **Registry:** Image storage (GHCR, Docker Hub, etc.).
- **Kubernetes:** Orchestrator that schedules containers across nodes.
- **Ingress:** HTTP/S routing into the cluster by hostname/path.
- **TLS:** Encryption for HTTPS.
- **GitOps:** Declarative cluster state driven from git with controllers like Argo CD or Flux.

---

## Closing reminder **(Human)**

No guide can guarantee security. On a **single NAS + app host**, the highest-leverage practices are still: **HTTPS**, **minimal exposed ports** (forward only what you need from the router), **patch regularly**, **non-root containers**, **sane mounts**, **treat CI secrets as production credentials**, **tested off-site backups**, and **review every manifest an AI generates** before you apply it to a machine reachable from the internet.

If you later move only the web tier to a **small rented VPS** or a **second PC**, you regain the separation benefits described in **§1.2**—optional, not required for the steps in this document.
