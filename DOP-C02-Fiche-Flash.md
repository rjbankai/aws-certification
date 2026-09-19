---
tags: [dop-c02, aws, devops, revision-express]
---

# DOP-C02 — Fiche Flash (veille et matin de l'examen)

> Une ligne = un réflexe. Le détail est dans les fiches domaine, liées depuis [[DOP-C02]].

## Mots-clés du scénario → réponse

### Déploiement ([[DOP-C02-SDLC-Automation]])
- *Zero downtime + rollback instantané* → **Blue/Green** (CodeDeploy, swap CNAME EB, alias Lambda)
- *Limiter le blast radius* → **Canary/Linear** + alarme CloudWatch + **auto-rollback**
- *Tester avant le trafic réel* → hook **`AfterAllowTestTraffic`** (ECS) / **`BeforeAllowTraffic`** (Lambda)
- *Pleine capacité pendant le déploiement EB, surcoût minimal* → **Rolling with additional batch**
- *Déploiement EB le plus sûr* → **Immutable**
- *Empêcher le push sur main (CodeCommit)* → **IAM policy** `Deny` + condition `codecommit:References`
- *Secrets dans le build* → `parameter-store:` / `secrets-manager:` dans le `buildspec`
- *Pipeline cross-compte* → **CMK KMS + bucket policy + rôle cross-compte**
- *Construire des images Docker dans CodeBuild* → **mode privileged**
- *Centraliser les dépendances npm/pip* → **CodeArtifact** (upstream)
- *ApplicationStop échoue au déploiement* → `--ignore-application-stop-failures`

### IaC et configuration ([[DOP-C02-Configuration-Management-IaC]])
- *Baseline sur tous les comptes, y compris futurs* → **StackSets service-managed** + auto-deployment sur l'OU
- *Valeur partagée entre stacks d'une autre région* → **custom resource Lambda**
- *Attendre que l'instance soit configurée* → **CreationPolicy + cfn-signal**
- *Rolling update d'un ASG via CFN* → **UpdatePolicy `AutoScalingRollingUpdate`**
- *Protéger une RDS pendant les updates CFN* → **stack policy** + `DeletionPolicy`/`UpdateReplacePolicy: Snapshot|Retain`
- *Self-service contrôlé pour les devs* → **Service Catalog** + launch constraint
- *Dérive de config sur les instances* → **SSM State Manager**
- *Patcher le parc* → **Patch Manager** + baseline + Maintenance Window
- *Plus de SSH/bastion* → **Session Manager**
- *Instance absente de Fleet Manager* → agent SSM · rôle IAM · réseau (NAT / endpoints)
- *AMI durcie, testée, distribuée* → **EC2 Image Builder**
- *Nouvelle AMI, remplacer la flotte* → **ASG instance refresh**
- *OpsWorks dans une option* → distracteur (fin de vie) → **SSM**

### Résilience ([[DOP-C02-Resilient-Cloud-Solutions]])
- *RTO/RPO + budget* → la stratégie DR **la moins chère qui tient** (Backup → Pilot Light → Warm Standby → Active/Active)
- *Failover en secondes, DNS trop lent, IP fixes* → **Global Accelerator**
- *DR base relationnelle cross-région* → **Aurora Global Database** (RPO ~1 s, RTO < 1 min)
- *NoSQL actif/actif multi-région* → **DynamoDB Global Tables**
- *Backups indestructibles* → **Backup Vault Lock compliance** / S3 Object Lock
- *Trop de connexions DB (Lambda, failover)* → **RDS Proxy**
- *ASG ne remplace pas l'instance dont l'appli est plantée* → health check type **ELB**
- *Valider la bascule DR* → **FIS** · *vérifier les objectifs RTO/RPO* → **Resilience Hub**

### Monitoring ([[DOP-C02-Monitoring-and-Logging]])
- *Mémoire / disque EC2* → **CloudWatch agent**
- *Alerte sur un mot dans les logs* → **metric filter** + alarme
- *Logs en temps réel vers OpenSearch / centralisés multi-comptes* → **subscription filter** → Kinesis/Firehose
- *Trop d'alertes* → **composite alarm** · *faux positifs cycliques* → **anomaly detection**
- *Détecter une panne avant les utilisateurs* → **Synthetics canary**
- *Métriques custom depuis Lambda sans appel API* → **EMF**
- *Dashboards/traces de tous les comptes* → **cross-account observability**
- *Prouver que les logs d'audit sont intacts* → **log file validation** + Object Lock + compte dédié

### Incidents ([[DOP-C02-Incident-and-Event-Response]])
- *Réagir à un appel d'API / un événement AWS* → **EventBridge** (jamais polling/cron)
- *Clé IAM exposée* → **AWS Health** `AWS_RISK_CREDENTIALS_EXPOSED` → automatisation
- *Rejouer des événements* → **EventBridge archive + replay**
- *Échecs Lambda asynchrone* → **Destinations** `OnFailure` · *SQS* → DLQ sur la **file** + `ReportBatchItemFailures`
- *Record Kinesis bloquant* → **bisect** + retries max + on-failure destination
- *Astreinte, escalade, runbook* → **Incident Manager**
- *Anomalies sans seuils* → **DevOps Guru**
- *Stack en UPDATE_ROLLBACK_FAILED* → **ContinueUpdateRollback**
- *ECS ne pull pas l'image* → **task execution role** / réseau vers ECR

### Sécurité ([[DOP-C02-Security-and-Compliance]])
- *Interdire partout, même aux admins* → **SCP**
- *Devs créent des rôles sans escalade* → **permission boundary**
- *Bucket accessible uniquement par mon Org* → `aws:PrincipalOrgID`
- *S3 uniquement depuis le VPC* → gateway endpoint + `aws:SourceVpce`
- *Menace* → **GuardDuty** · *CVE* → **Inspector** · *PII* → **Macie** · *agrégation* → **Security Hub** · *enquête* → **Detective**
- *Clé KMS cross-compte* → **customer managed key** + key policy
- *Bloquer une IP* → **NACL** ou **WAF**
- *Règles WAF/SG sur toute l'Org* → **Firewall Manager**
- *Instance compromise* → SG vide + snapshot + ne pas terminer

## Chiffres à connaître

| Valeur | Contexte |
|---|---|
| 15 min | Durée max Lambda |
| 2 retries | Lambda asynchrone par défaut |
| 12 h | Délai max d'un export CloudWatch Logs vers S3 |
| 90 j | Event history CloudTrail |
| 35 j | PITR DynamoDB / rétention max des backups auto RDS |
| 365 j | Rétention max Kinesis Data Streams |
| 15 min | SLA S3 Replication Time Control |
| 60–120 s | Failover RDS Multi-AZ (instance) |
| < 1 min / ~1 s | RTO / RPO Aurora Global Database |
| 1 h | Timeout par défaut d'une custom resource CFN |
| 45 j | Premiers avertissements d'expiration ACM |
| 7–30 j | Délai de suppression d'une clé KMS |
| 4 Ko / 64 Ko | Parameter Store standard / Secrets Manager |

## Services « une phrase »

- **App Runner** : déployer un conteneur/du code web sans gérer d'infra (plus simple que ECS/Fargate).
- **Proton** : templates d'infra + pipeline gérés par une équipe plateforme pour les équipes dev.
- **Compute Optimizer** : recommandations de dimensionnement (EC2, ASG, Lambda, EBS, ECS).
- **CodeGuru Reviewer / Profiler** : revue de code avant merge / profiling en prod.
- **AWS Artifact** : rapports de conformité d'AWS · **Audit Manager** : preuves d'audit continues.
