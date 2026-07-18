# CI/CD Google Cloud va domain `mchienn.dev`

## Kien truc de xuat

```text
GitHub PR -> Cloud Build: pytest + typecheck + frontend build
GitHub main -> Cloud Build -> Artifact Registry -> 3 Cloud Run services
                                            -> Firebase Hosting (React dist)
Internet -> mchienn.dev -> Firebase Hosting CDN
                         |- /adk-api/**     -> athena-adk
                         |- /api/**         -> athena-auth
                         `- /booking-api/** -> athena-booking
```

Dung Firebase Hosting cho React va rewrite API sang Cloud Run. Browser chi goi origin `https://mchienn.dev`, nen khong phai mo CORS production. Khong dung Cloud Run Domain Mapping (dang Preview/availability han che); demo chua can Global External Application Load Balancer. De xuat dung region `asia-southeast1` cho Artifact Registry, Cloud Run va Cloud Build trigger; Firestore vector dang `global` thi giu nguyen.

## Secret va IAM

Tao 3 runtime service account rieng: `sa-athena-adk`, `sa-athena-auth`, `sa-athena-booking`. Cap Firestore/Vertex AI (neu dung), Secret Manager Secret Accessor va cac quyen toi thieu dung voi tung service. Cloud Build service account can Artifact Registry Writer, Cloud Run Admin, Service Account User tren runtime SAs va Firebase Hosting Admin.

Luu `OPENAI_API_KEY`, `JWT_SECRET_KEY` va cac key nhay cam trong Secret Manager. Bien cau hinh khong nhay cam co the dat environment variables. Khong dat `GOOGLE_APPLICATION_CREDENTIALS` tren Cloud Run: Google client libraries dung service identity cua Cloud Run.

Bat buoc xu ly truoc public deploy:

1. Bat buoc `JWT_SECRET_KEY`; bo fallback hard-code va rotate key cu.
2. Bo `POST /patients/mock` khoi production router.
3. Khong dua SQLite `schedule.db` vao Cloud Run; filesystem container la ephemeral. Lich/appointment production phai o Firestore hay database dich vu.

## Thao tac Console mot lan (can chu GCP project)

1. Tao/chon Google Cloud project co billing, add vao Firebase; ghi `PROJECT_ID` va `PROJECT_NUMBER`.
2. Enable Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Firestore, Vertex AI (neu dung), IAM Service Account Credentials va Firebase APIs theo Console.
3. Tao Artifact Registry Docker repository `athena` o `asia-southeast1`.
4. Tao 3 runtime service account va IAM least-privilege nhu tren.
5. Tao Secret Manager secrets, them gia tri tren Console, gan vao dung Cloud Run service. Runtime SA cua service do phai co Secret Accessor.
6. Firebase Console: khoi tao Hosting site. Site deploy `frontend/dist` va da co Firestore rules/indexes.
7. Cloud Build > Repositories/Triggers: ket noi GitHub repository. Chu GitHub/GCP phai phe duyet OAuth/GitHub App.
8. Tao 2 triggers:
   - `athena-pr-check`: pull request, chay test/typecheck/build, khong deploy.
   - `athena-prod-main`: push `main`, deploy sau khi checks thanh cong.
9. Bat budget alert va Monitoring alert cho Cloud Run 5xx, latency, restart va Cloud Build failure. Demo dat `min instances=0` va max instances de gioi han chi phi.

Trang thai hien tai: connection `athena-github` da `COMPLETE`, nhung GitHub App
installation `147324459` chua duoc cap repo `binhdaumoi0309-hub/Athena`. Mo
`https://github.com/settings/installations/147324459`, chon **Configure**, sau
do them repo **Athena** vao Repository access. Khong can tao token hay key moi.
Sau buoc nay moi co the dang ky repository va tao hai trigger tren.

Luu y: `ruff check .` hien fail 107 loi. Chay pytest/typecheck/build trong PR trigger ngay; chi bat ruff blocking gate sau khi da sua hoac baseline co chu dich.

## Phan viec can them vao repository truoc khi bat auto-deploy

Repo da co Dockerfile, `cloudbuild.yaml`, `cloudbuild.ci.yaml`, Cloud Run runtime entrypoint va Firebase Hosting rewrites. Cac file nay can duoc review/merge truoc khi bat trigger. Phan da implement gom:

1. Dockerfile Python dung chung, build ba image voi command runtime rieng: ADK API, auth FastAPI va booking FastAPI.
2. `cloudbuild.yaml`: test backend/frontend; build/push image tag `$COMMIT_SHA`; deploy ba Cloud Run services voi runtime SA va Secret Manager bindings; build/deploy Firebase Hosting.
3. Mo rong `frontend/firebase.json`: Hosting `public: "dist"`, SPA fallback, rewrite `/adk-api/**`, `/api/**`, `/booking-api/**` sang dung Cloud Run service/region; giu Firestore config.
4. Dung frontend production env theo path cung origin, khong hard-code `localhost`.
5. Them health/smoke test sau deploy va quy trinh rollback Cloud Run revision.

Khong bat auto-deploy truoc khi review PR nay: repo co ba Python server doc lap, can chot command runtime va endpoint cong khai cua tung service.

## Chuyen DNS tu Name.com sang Cloudflare

Kien truc da chot: Name.com tiep tuc la registrar; Cloudflare Free la
authoritative DNS; Firebase Hosting van phuc vu frontend, CDN va SSL. Khong bat
Cloudflare proxy cho record Firebase trong giai doan xac minh; de **DNS only**
(may xam), vi Firebase can nhin thay A/CNAME truc tiep de cap certificate.

Firebase da tao:

- `mchienn.dev` phuc vu site chinh.
- `www.mchienn.dev` redirect HTTP 301 ve `mchienn.dev`.

DNS cong khai truoc migration chi co A cho apex va `www` tro
`91.195.240.94`; khong thay MX/TXT/CAA. Van phai kiem tra bang Cloudflare scan
truoc khi doi nameserver.

### Buoc can chu domain lam mot lan

1. Dang nhap/tao Cloudflare, chon **Add a domain** > `mchienn.dev` > Free plan.
2. O man hinh DNS records cua Cloudflare, dat chinh xac:

   | Type | Name | Content | Proxy |
   | --- | --- | --- | --- |
   | A | `@` | `199.36.158.100` | DNS only |
   | TXT | `@` | `hosting-site=project-5d300c02-d165-4037-b6f` | n/a |
   | CNAME | `www` | `project-5d300c02-d165-4037-b6f.web.app` | DNS only |

   Xoa hai A cu `@`/`www` tro `91.195.240.94`. Giu moi MX, SPF, DKIM, DMARC
   neu Cloudflare scan tim thay.
3. Cloudflare se cap hai nameserver rieng. Truoc khi doi, kiem tra DNSSEC tai
   Name.com; neu dang bat thi tat DNSSEC tam thoi.
4. Name.com > **My Domains > mchienn.dev > Manage Nameservers**. Xoa bon
   nameserver Name.com hien tai (`ns1kwy`, `ns2dky`, `ns3cfp`, `ns4dfh`) va
   them dung hai nameserver Cloudflare cap, sau do Save Changes.
5. Cho Cloudflare zone thanh **Active**, sau do bat lai DNSSEC bang DS record
   Cloudflare cap neu muon. Firebase co the mat toi 24 gio de cap SSL va chuyen
   hai custom domain sang `Connected`.

Khong dat Cloudflare API token trong repo hay Cloud Build. DNS khong nam trong
CI/CD: deploy moi chi cap nhat Firebase Hosting/Cloud Run, khong dong vao
nameserver. Neu can tu dong quan ly DNS sau nay, dung Cloudflare API token scope
`Zone:DNS Edit` cho rieng `mchienn.dev` va luu trong Secret Manager.

## Checklist truoc public demo

- [ ] Secret khong nam trong Git, Docker image hay Cloud Build log/substitution.
- [ ] JWT fallback va mock endpoint da ra khoi production.
- [ ] Ba Cloud Run services dung runtime identity rieng, least-privilege.
- [ ] Frontend goi API qua Hosting rewrites, khong goi localhost.
- [ ] PR trigger pass pytest, typecheck, frontend build; ruff duoc xu ly/baselined.
- [ ] Main trigger deploy commit SHA, smoke test va co rollback procedure.
- [ ] `mchienn.dev` va www co SSL Connected; DNS email records con nguyen.
- [ ] Da bat budget/alert; khong dua PHI that vao demo khi chua co compliance approval.

## Tai lieu chinh thuc

- [Cloud Build deploy Cloud Run](https://cloud.google.com/build/docs/deploying-builds/deploy-cloud-run)
- [Cloud Build triggers](https://cloud.google.com/build/docs/automating-builds/create-manage-triggers)
- [Cloud Run service identity](https://cloud.google.com/run/docs/configuring/services/service-identity)
- [Cloud Run secrets](https://cloud.google.com/run/docs/configuring/services/secrets)
- [Firebase Hosting rewrite Cloud Run](https://firebase.google.com/docs/hosting/cloud-run)
- [Firebase custom domain](https://firebase.google.com/docs/hosting/custom-domain)
- [Cloudflare full DNS setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/)
- [Name.com change nameservers](https://www.name.com/support/articles/205934547-changing-nameservers-for-dns-management)
- [Name.com DNS records](https://www.name.com/support/articles/206127137-adding-dns-records-and-templates)

## Chi tiet: runtime service la gi?

**Runtime service account** la danh tinh ma mot Cloud Run container mang theo khi dang xu ly request. Vi du `athena-auth` goi Firestore thi Google kiem tra quyen cua `sa-athena-auth`, khong kiem tra quyen cua nguoi da deploy hay cua Cloud Build.

Day la ba danh tinh khac nhau:

| Danh tinh | Dung luc nao | Khong duoc cap quyen gi |
| --- | --- | --- |
| Tai khoan Google cua ban | Tao project, billing, IAM, trigger | Khong dung de app chay |
| `sa-cloudbuild-deploy` | Build image va deploy revision | Khong doc Firestore/secret runtime |
| `sa-athena-*` | Container dang chay truy cap Firestore, Vertex, secret | Khong deploy service hay sua IAM |

Khong tai JSON key cho runtime service account. Cloud Run tu cap short-lived credential cho container qua metadata server. Day la ly do khong dat `GOOGLE_APPLICATION_CREDENTIALS` o Cloud Run.

### “Cap Firestore” nghia la gi?

Day la cap **IAM cho server code**, khong phai sua `firestore.rules`.

- Browser Firebase SDK bi gioi han boi `firestore.rules`.
- Python server dung Google server client library thi **bypass Firestore Security Rules**, va duoc phep theo IAM cua runtime service account.
- `roles/datastore.user` cho phep doc/ghi documents; dung cho backend nay. Khong cap `roles/datastore.owner` hay Project Editor chi de app doc/ghi data.
- Role nay van ap dung toan database; neu can tach that su theo collection, can tach project/database hoac thiet ke service boundary, khong dua vao Firestore Rules cho backend.

### Tao runtime service account trong Console

Lam lai 3 lan cho `athena-adk`, `athena-auth`, `athena-booking`:

1. Google Cloud Console > **IAM & Admin > Service Accounts** > **Create service account**.
2. Ten: `sa-athena-adk` (Console tu them email dang `sa-athena-adk@PROJECT_ID.iam.gserviceaccount.com`). Ghi ro description: Runtime identity for Athena ADK Cloud Run.
3. Bam Create and Continue. Khong tao key, khong them user access o buoc nay.
4. Vao **IAM & Admin > IAM** > tim service account vua tao > **Edit principal** > Add roles:
   - Ca 3 service: **Cloud Datastore User** (`roles/datastore.user`).
   - Chi `sa-athena-adk`: **Vertex AI User** (`roles/aiplatform.user`) neu service goi Vertex/embedding bang ADC.
   - Chi service dung secret: them **Secret Manager Secret Accessor** (`roles/secretmanager.secretAccessor`) o tung secret; uu tien scope o Secret Manager > secret > Permissions, khong cap tren ca project.
5. Khong cap Cloud Run Admin, Artifact Registry Writer, Owner, Editor hay Service Account User cho runtime accounts.

Sau nay, luc deploy `athena-auth`, chon **Security > Service account > sa-athena-auth**. Kiem tra tab Revisions cua Cloud Run de chac revision moi van dung dung identity.

### Tao Secret Manager va gan vao Cloud Run

Tao cac secret rieng, vi du `jwt-secret-key`, `openai-api-key` (chi neu thuc su dung). Nhap value trong Console: **Security > Secret Manager > Create secret**. Khong dung terminal command co the luu secret vao history.

Voi moi secret:

1. Mo secret > **Permissions** > Grant access.
2. Them runtime service account can doc secret, role **Secret Manager Secret Accessor**.
3. Mo Cloud Run service > **Edit and deploy new revision** > Containers > Variables & Secrets > **Reference a secret**.
4. Dat env var dung ten ma code doc, vi du `JWT_SECRET_KEY`; chon secret va version. Pin mot version so cho environment variable de rollout co the rollback duoc.
5. Deploy revision. Neu runtime identity khong co Secret Accessor, instance se khong khoi dong.

Khong cap secret cho `sa-cloudbuild-deploy` neu pipeline chi can gan reference secret vao Cloud Run; Cloud Run se kiem tra quyen cua runtime identity.

### Tao Cloud Build deploy identity

Tao `sa-cloudbuild-deploy` tuong tu Service Accounts. Sau do grant:

1. **Artifact Registry Writer** tren repository `athena` (scope repository neu Console cho phep).
2. **Cloud Run Admin** tren project (hoac tung service sau khi service ton tai).
3. **Service Account User** tren *tung* `sa-athena-*`. Quyen nay cho phep Cloud Build gan runtime identity vao revision; no khong cho phep doc secret cua identity do.
4. **Firebase Hosting Admin** va **API Keys Viewer** neu build dung Firebase CLI de deploy Hosting.

Voi custom build service account, Cloud Build service agent `service-PROJECT_NUMBER@gcp-sa-cloudbuild.iam.gserviceaccount.com` can **Service Account Token Creator** tren `sa-cloudbuild-deploy`. Day la cau hinh bat buoc Google neu dung user-specified service account. Khong xoa role Cloud Build Service Agent cua Google-managed service agent.

### Tao Cloud Run service trong Console (lan dau)

Lam sau khi PR da co Dockerfile/image:

1. Cloud Run > **Create service**.
2. Chon image trong Artifact Registry, vi du `asia-southeast1-docker.pkg.dev/PROJECT_ID/athena/athena-auth:COMMIT_SHA`.
3. Dat service name lan luot `athena-adk`, `athena-auth`, `athena-booking`; region `asia-southeast1`.
4. Trong Container: app phai listen `0.0.0.0:$PORT`; Cloud Run tu set `PORT`. Khong hard-code port localhost.
5. Trong Security: gan dung runtime service account; ingress **All** cho demo co Firebase Hosting rewrite.
6. Authentication: Firebase Hosting rewrite sang Cloud Run theo huong dan Firebase yeu cau service allow unauthenticated invocation. Bao ve endpoint nhay cam o application level bang JWT/OTP/rate limit; khong dua secret trong request.
7. Dat `min instances=0`, `max instances` hop ly (vi du 2-5 demo), timeout phu hop. Firebase Hosting co timeout 60 giay khi rewrite sang Cloud Run; endpoint ADK dai hon phai streaming/toi uu hay goi Cloud Run URL truc tiep theo thiet ke khac.
8. Gan variables/secrets, deploy, xem Logs. Test `/` hay `/docs` truoc khi tao Hosting rewrite.

`asia-southeast1` duoc Firebase Hosting ho tro rewrite sang Cloud Run. Dung `pinTag: true` trong Firebase rewrite neu muon static assets va Cloud Run revision rollback cung nhau; luu y Cloud Run tags co gioi han, nen khong luu vo han cac Hosting releases.

### Checks va rollback

PR trigger chi test. Main trigger deploy image tag bat bien `$COMMIT_SHA`, sau do:

1. Goi health endpoint cua ca 3 service.
2. Deploy Hosting sau khi API healthy.
3. Neu smoke test loi, traffic Cloud Run van co the pin ve revision truoc trong Cloud Run > service > Revisions > **Manage traffic**. Ghi lai commit SHA va revision name trong release note.
4. Khong tu dong rollback tren loi 4xx cua nguoi dung; chi rollback khi health check/5xx regression xac nhan.
