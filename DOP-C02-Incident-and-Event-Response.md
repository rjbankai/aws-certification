---
tags: [dop-c02, aws, devops, incident, events, troubleshooting]
domaine: "5 — Incident and Event Response (14% de l'examen)"
---

# DOP-C02 — Domaine 5 : Incident and Event Response

> Poids : **14%**.
> Trois axes : (1) gérer les **sources d'événements** et y réagir, (2) appliquer des **changements de configuration** en réponse à un événement, (3) **dépanner** les échecs système et applicatifs.
> Angle des questions : « un événement se produit → quelle est la chaîne **la plus automatisée** pour détecter, notifier et corriger ? » ou « le déploiement / la stack échoue → quelle est la **cause racine** ? »

---

## 1. Les sources d'événements

| Source | Ce qu'elle émet | À retenir |
|---|---|---|
| **EventBridge** | Le bus central : événements de ~tous les services AWS, SaaS, custom (`PutEvents`) | Règles sur **pattern** ou **schedule**, cibles multiples, **archive + replay**, bus **cross-compte**, **Pipes** (source → filtre → enrichissement → cible) |
| **CloudTrail → EventBridge** | Chaque appel d'API (`AWS API Call via CloudTrail`) | Réagir **en quasi temps réel** à `DeleteBucket`, `StopLogging`, `AuthorizeSecurityGroupIngress`… |
| **AWS Health** | Pannes AWS, maintenances planifiées, retraites d'instances, **clés exposées** (`AWS_RISK_CREDENTIALS_EXPOSED`) | Source `aws.health` dans EventBridge. **Organizational view** pour agréger tous les comptes. |
| **Trusted Advisor** | Checks coût / sécu / limites de service | Événements disponibles **uniquement en us-east-1**. Checks complets = support **Business** ou supérieur. |
| **CloudWatch Alarms** | Changement d'état (`ALARM`) | Actions directes ou événement EventBridge |
| **AWS Config** | Changement de conformité d'une ressource | Remédiation SSM Automation ou EventBridge → Lambda |
| **S3 Event Notifications** | Objet créé / supprimé | Cibles natives : SNS, SQS, Lambda. Pour filtrer finement ou viser d'autres cibles → **activer EventBridge sur le bucket**. |
| **GuardDuty / Security Hub / Inspector** | Findings | Tous envoient leurs findings vers EventBridge |

**Pattern universel d'auto-remédiation** : *source → règle EventBridge (pattern) → Lambda / SSM Automation / Step Functions → correction + SNS pour notifier.*

Exemples qui tombent :
- **Clé IAM exposée publiquement** → événement AWS Health `AWS_RISK_CREDENTIALS_EXPOSED` → EventBridge → Lambda / Step Functions : désactiver la clé, lister l'activité récente dans CloudTrail, notifier.
- **Instance EC2 en retraite planifiée** (Health `scheduled change`) → EventBridge → SSM Automation stop/start pour migrer sur un nouvel hôte.
- **Quelqu'un désactive CloudTrail** (`StopLogging`) → EventBridge → Lambda qui relance `StartLogging` + alerte.
- **Security group ouvert sur 0.0.0.0/0:22** → Config rule `restricted-ssh` → remédiation automatique SSM.

## 2. Messagerie et traitement asynchrone — gérer les échecs

| Service | En cas d'échec | Réglage clé |
|---|---|---|
| **SQS** | Message réapparaît après le **visibility timeout** | `maxReceiveCount` → **DLQ** ; **redrive** pour renvoyer depuis la DLQ |
| **SNS** | Retries selon le protocole | **DLQ par souscription** (une file SQS) |
| **Lambda asynchrone** (S3, SNS, EventBridge) | **2 retries** par défaut (0–2), âge max de l'événement jusqu'à 6 h | **Destinations** `OnFailure` / `OnSuccess` (SQS, SNS, Lambda, EventBridge) — préférées à la DLQ Lambda, plus riches (contexte d'erreur) |
| **Lambda + SQS** (event source mapping) | Tout le batch revient dans la file | **`ReportBatchItemFailures`** → ne rejouer que les messages en échec. DLQ configurée **sur la file SQS**, pas sur la Lambda. |
| **Lambda + Kinesis / DynamoDB Streams** | Le shard est **bloqué** tant que le batch échoue | `BisectBatchOnFunctionError`, `MaximumRetryAttempts`, `MaximumRecordAgeInSeconds`, **on-failure destination** |
| **EventBridge** | Retries jusqu'à 24 h | **DLQ** (SQS) sur la cible, **archive + replay** |
| **Step Functions** | Selon la définition | `Retry` (backoff) + `Catch` par état |

⚠️ **Lambda : Destinations ≠ DLQ.** Les destinations ne s'appliquent qu'aux invocations **asynchrones** (et aux event source mappings pour `OnFailure`). Pour SQS → la DLQ se met sur la **file**.

## 3. Outils de gestion d'incident

- **Systems Manager Incident Manager** : **response plans** (qui engager, quel runbook lancer), **contacts** et **escalation plans**, canaux de chat, **runbooks SSM Automation**, analyse post-incident. Déclenché par une **alarme CloudWatch** ou une **règle EventBridge**.
- **OpsCenter** : centralise les **OpsItems** (problèmes opérationnels) avec contexte, ressources liées et runbooks associés. Cible possible d'une alarme ou d'EventBridge.
- **Amazon DevOps Guru** : détection d'anomalies opérationnelles par **ML** (reactive et proactive insights), sans définir de seuils. Réponse à « détecter les anomalies sans configurer d'alarmes manuellement ». **DevOps Guru for RDS** pour les problèmes de performance base de données.
- **AWS Health Dashboard** : « est-ce AWS qui est en panne ou moi ? ».
- **Fleet Manager** : vue et actions sur les instances gérées par SSM.

## 4. Dépannage par service — les causes classiques

### CodeDeploy
- Agent absent/arrêté · **instance profile** sans accès S3 · **service role** CodeDeploy manquant · `appspec.yml` pas à la racine.
- `ApplicationStop` échoue → script de l'**ancienne** révision → `--ignore-application-stop-failures`.
- Échec `HEALTH_CONSTRAINTS` → trop d'instances en échec par rapport au minimum de la deployment config.
- Logs : `/var/log/aws/codedeploy-agent/` et `/opt/codedeploy-agent/deployment-root/deployment-logs/`.

### CloudFormation
- **`UPDATE_ROLLBACK_FAILED`** (ressource modifiée à la main, par ex.) → corriger manuellement puis **`ContinueUpdateRollback`**, avec `--resources-to-skip` si besoin.
- **`DELETE_FAILED`** (bucket S3 non vide, ressource utilisée ailleurs) → vider / retirer la dépendance, ou relancer le delete avec **`RetainResources`**.
- **Custom resource** qui ne répond pas → stack bloquée jusqu'au **timeout (1 h par défaut)** → toujours renvoyer SUCCESS/FAILED, même en cas d'exception.
- **`CreationPolicy` timeout** → `cfn-signal` jamais envoyé (script user data en erreur, pas d'accès réseau vers l'endpoint CFN, mauvais nom de ressource).
- Garder les ressources pour debugger : `--disable-rollback` (ou *Preserve successfully provisioned resources*).

### Auto Scaling / EC2
- Instances lancées puis terminées en boucle → **health check grace period** trop courte, ou health check `ELB` qui échoue (appli pas prête, mauvais port/chemin, security group).
- Instance en échec non remplacée → health check type `EC2` au lieu de `ELB`.
- Investiguer une instance avant qu'elle soit terminée → **lifecycle hook** `Terminating:Wait`, **mise en Standby** (`EnterStandby`), ou **suspendre le process `ReplaceUnhealthy`**. (⚠️ la *scale-in protection* ne protège pas d'un remplacement pour cause de mauvaise santé.)
- Échec au lancement → quota, AMI indisponible, launch template invalide, capacité insuffisante dans l'AZ (→ multi-AZ / types d'instances multiples).

### ECS
- **Task execution role** = rôle utilisé par l'**agent** pour **puller l'image ECR**, écrire les logs CloudWatch, lire les secrets. **Task role** = permissions de **ton application**. ⚠️ « CannotPullContainerError » → execution role ou réseau (NAT / VPC endpoints ECR + S3).
- Tâche qui s'arrête → consulter le **stopped reason** + logs `awslogs`.
- Déploiement qui échoue en boucle → **deployment circuit breaker** avec rollback automatique.

### Lambda
- **Timeout** (max 15 min) · **throttling** (429, concurrence épuisée → reserved concurrency) · Lambda dans un VPC sans **NAT** → pas d'accès Internet ni aux API AWS publiques (→ NAT ou VPC endpoints) · permissions manquantes sur le **rôle d'exécution**.

### Elastic Beanstalk
- `eb logs` / demander les logs depuis la console (tail ou bundle), **enhanced health** pour les causes. Logs persistables vers S3/CloudWatch.

---

## Réflexes pour répondre aux questions

1. **« Réagir immédiatement à un appel d'API »** → **EventBridge** (événement CloudTrail), pas un scan des logs S3.
2. **« Être notifié d'un problème AWS affectant mes ressources »** → **AWS Health** + EventBridge (organizational view si multi-comptes).
3. **« Clé d'accès exposée sur GitHub »** → événement Health `AWS_RISK_CREDENTIALS_EXPOSED` → automatisation qui désactive la clé.
4. **« Messages Lambda/SQS perdus ou traités en échec »** → DLQ sur la **file SQS** + `ReportBatchItemFailures`.
5. **« Événements asynchrones Lambda en échec, garder le contexte »** → **Lambda Destinations** `OnFailure`.
6. **« Un record Kinesis bloque tout le shard »** → `BisectBatchOnFunctionError` + `MaximumRetryAttempts` + on-failure destination.
7. **« Rejouer des événements perdus »** → **EventBridge archive + replay**.
8. **« Orchestrer la réponse à incident : astreinte, escalade, runbook »** → **Incident Manager**.
9. **« Détecter des anomalies sans définir de seuils »** → **DevOps Guru**.
10. **« Stack bloquée en UPDATE_ROLLBACK_FAILED »** → corriger puis **ContinueUpdateRollback** (skip resources).
11. **« ECS ne peut pas puller l'image »** → **task execution role** / connectivité ECR.
12. **« Garder une instance défaillante pour l'analyser »** → lifecycle hook / standby / suspendre `ReplaceUnhealthy`.

---

## Mémo dernière minute — les 5 points à réviser en priorité

### 1. EventBridge est la réponse par défaut
Événement d'un service AWS, appel d'API (via CloudTrail), finding sécurité, changement d'état d'alarme, événement Health → **règle EventBridge** → Lambda / SSM Automation / Step Functions / SNS. Polling ou cron = mauvaise réponse.

### 2. Lambda et les échecs
Asynchrone → **2 retries** + **Destinations** (préférées) ou DLQ. SQS → DLQ **sur la file** + `ReportBatchItemFailures`. Kinesis/DynamoDB Streams → **bisect** + retries max + on-failure destination.

### 3. AWS Health et Trusted Advisor
Health = événements AWS qui **te concernent** (pannes, retraites, clés exposées) — organizational view. Trusted Advisor = **bonnes pratiques** et limites de service — événements en **us-east-1** uniquement.

### 4. Dépannage CloudFormation
`UPDATE_ROLLBACK_FAILED` → **ContinueUpdateRollback**. `DELETE_FAILED` → **RetainResources** ou vider le bucket. Custom resource muette → timeout 1 h. `cfn-signal` absent → échec de la `CreationPolicy`.

### 5. Task role vs task execution role (ECS)
**Execution role** = ECS lui-même (pull ECR, logs, secrets au démarrage). **Task role** = ton code (appeler S3, DynamoDB…).
