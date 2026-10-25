# First AWS deployment with HTTPS and Google/GitHub OAuth

This is a controlled single-EC2 deployment using the existing Docker Compose application, behind an AWS Application Load Balancer (ALB). It is not the final high-availability production topology. No AWS resources have been provisioned or tested by this guide. EC2, EBS, ALB, DNS and traffic incur AWS charges; use the company's approved account/region and a billing budget.

## 1. Domain and certificate

Use a company subdomain such as `app.example.com`. You need permission to edit its DNS. In AWS Certificate Manager, request a public certificate for that hostname **in the same region as the ALB**. Complete DNS validation and wait until Issued. You do not install this certificate inside Docker; the ALB terminates HTTPS. A public EC2 IP alone does not supply the HTTPS domain needed here.

## 2. Server and network

Launch Ubuntu Server 24.04 LTS, x86_64, on a `t3.large` (2 vCPU / 8 GiB) or equivalent starting size, with encrypted 40+ GiB gp3 EBS. This is a starting configuration to measure, not a load-tested capacity guarantee. Use configured remote AI providers; no model download is required. Keep the EC2 and ALB in the same VPC. Record the VPC CIDR from the VPC console.

Create two security groups:

| Security group | Inbound rule |
| --- | --- |
| ALB | TCP 443 from users; TCP 80 only for HTTPS redirection |
| EC2 application | TCP 8080 **from the ALB security group only**; TCP 22 only from your current IP if using SSH |

Do not expose PostgreSQL 5432, API 8000, compiler 8070 or local web 3000. Give the server the outbound access needed to install containers and call selected fixed provider endpoints. Connect using SSH from your computer or an appropriately configured AWS Systems Manager session; do not place AWS access keys on the instance.

From Windows Command Prompt, with the private SSH key downloaded when launching the instance:

```cmd
ssh -i "C:\path\evolvyn.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

The commands below run in the EC2 Ubuntu shell. Install Docker Engine and the Compose plugin using Docker's Ubuntu instructions: https://docs.docker.com/engine/install/ubuntu/. Use Compose **2.24.4 or newer** for the AWS overlay's `!override` ports. Use `sudo docker` unless your account has Docker permissions.

```bash
sudo apt-get update
sudo apt-get install -y git python3
git clone https://github.com/25955A0512/Evolvyn.git
cd Evolvyn
python3 scripts/prepare_deployment.py
nano .local/deploy.env
```

A private GitHub repository requires your own read authorization. Do not put GitHub tokens in clone URLs or shell history.

## 3. Private server configuration

In the existing ignored `.local/deploy.env`, change only these nonsecret settings to your real values. Preserve all generated passwords and vault/compiler keys:

```dotenv
PUBLIC_ORIGIN=https://app.example.com
ALLOWED_HOSTS=app.example.com,localhost,127.0.0.1
COOKIE_SECURE=1
EVOLVYN_TRUSTED_PROXY_CIDR=172.31.0.0/16
```

The CIDR above is **only an example**. Use the actual VPC CIDR containing the ALB. The AWS-specific nginx template trusts that proxy network, takes the final ALB-appended client IP and sends HTTPS metadata to the API. This depends on the EC2 listener being reachable only through the ALB security group. Do not trust arbitrary internet proxies.

Start the existing app with the AWS overlay:

```bash
sudo docker compose --env-file .local/deploy.env -f compose.yaml -f compose.aws.yaml up -d --build --wait
sudo docker compose --env-file .local/deploy.env -f compose.yaml -f compose.aws.yaml ps
```

Use both Compose files for subsequent cloud start/update commands. The compiler remains private; database and vault volumes persist. Never run `down -v` against data you want to keep.

## 4. ALB and DNS

1. Create an **instance** target group using **HTTP port 8080**; register the EC2 instance. Set health-check path to `/healthz`, success code 200. This checks nginx, not database/API health.
2. Create an internet-facing Application Load Balancer in at least two public subnets in different availability zones. Attach the ALB security group.
3. Configure listener **HTTPS 443** with the issued ACM certificate, forwarding to the target group. Configure **HTTP 80 → HTTPS 443** redirect. Set ALB idle timeout to 180 seconds for agent streaming.
4. In Route 53, create an Alias A record for `app.example.com` targeting the ALB. With another DNS provider, use its supported ALB alias or a CNAME for the subdomain. Do not point this app hostname directly at the EC2 public IP.
5. Wait for target health/DNS. Open `https://app.example.com`, then explicitly check `https://app.example.com/api/health` returns `{"status":"ok"}`. Verify a valid certificate and that HTTP redirects to HTTPS.

## 5. Register real OAuth applications

**Google:** open https://console.cloud.google.com/auth/clients, configure branding/audience, create a **Web application** OAuth client. Add your app's HTTPS origin where requested and this exact authorized redirect URI:

```
https://app.example.com/api/auth/oauth/google/callback
```

While the Google application is in Testing, add your intended users as test users. Complete Google's verification/publishing requirements before opening sign-in to a wider audience; do not imply approval is automatic.

**GitHub:** open https://github.com/settings/developers → OAuth Apps → New OAuth App. Homepage URL is your app origin. Authorization callback URL:

```
https://app.example.com/api/auth/oauth/github/callback
```

The same GitHub callback handles sign-in and the separately initiated read-only connector authorization. A sign-in grant does not silently connect repositories or authorize writes.

Enter application IDs/secrets **on the server**, with hidden secret input:

```bash
python3 scripts/configure_oauth.py --provider google --origin https://app.example.com
python3 scripts/configure_oauth.py --provider github --origin https://app.example.com
python3 scripts/configure_oauth.py --check
sudo docker compose --env-file .local/deploy.env -f compose.yaml -f compose.aws.yaml up -d --no-build --force-recreate api
```

Never paste client secrets into chat, source control, prompts or shell arguments. Configuration readiness is not proof of live provider acceptance. Client credentials, domain and callbacks must match the provider console exactly.

## 6. Verify the real journey

Use a private browser window. Sign up with Google, log out, sign in again and confirm the same account/workspace. Repeat with a different GitHub email or explicitly link GitHub from the original signed-in account settings. Existing email accounts are never automatically merged. Cancel authorization once and verify no session/account is created; retry normally. Test logout/session revocation. Inspect cookie metadata without copying its value: Secure, HttpOnly and the expected SameSite setting must be present.

For the GitHub connector, use Integrations → Connect GitHub separately, authorize, test the connection, invoke a permitted public-repository read, and disconnect. No private repository grant, repository write or other service connection is implied.

Set the business-agent default key in the **cloud instance's** Key vault and perform a small model test; the local machine's saved Gemini key is not automatically copied to AWS.

## 7. Data, backups and next production gates

A fresh server creates an empty database and a new vault key. To migrate existing data, use a private PostgreSQL backup/restore and preserve the **original vault key** in separately secured custody; do not restore encrypted credentials with a newly generated key. Do not overwrite an existing populated cloud database casually. Never upload database/env/key files to GitHub.

Back up the PostgreSQL data and vault key separately, encrypt backups, restrict access, and test restoration. EBS persistence alone is not a backup. Before real customer use, finish independent security review, recovery/MFA requirements, workload/cost checks and incident monitoring. Move PostgreSQL to private encrypted RDS with tested TLS/backups, deploy separate workers, and use managed secrets/observability as described in CLOUD_DEPLOYMENT.md. Existing local source compilation is not arbitrary generated-app execution; cloud hosting does not add that capability.
