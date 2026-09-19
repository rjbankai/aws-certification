---
tags: [dop-c02, aws, devops, monitoring, logging, observability]
domaine: "4 — Monitoring and Logging (15% de l'examen)"
---

# DOP-C02 — Domaine 4 : Monitoring and Logging

> Poids : **15%**.
> Trois axes : collecter/agréger/stocker, analyser pour détecter, automatiser la réaction.
> Angle des questions : « quelle est la **source de vérité** pour cette information, et comment la transformer en **alerte ou action automatique** ? »

---

## 1. CloudWatch Metrics & Alarms

- **Métriques** : namespace + **dimensions**. Résolution **standard = 1 min**, **high-resolution = 1 s** (custom uniquement, alarmes à 10 s/30 s).
- ⚠️ **Non disponibles par défaut sur EC2** : **mémoire**, **espace disque**, processus → nécessitent le **CloudWatch agent** (unifié : métriques + logs, config stockable dans **Parameter Store** et distribuée via SSM).
- **Custom metrics** : `PutMetricData`, ou **EMF (Embedded Metric Format)** — on écrit un JSON structuré dans les logs et CloudWatch en extrait des métriques (idéal Lambda/conteneurs, sans appel API supplémentaire).
- **Metric math** et **anomaly detection** (bande basée sur l'historique → bon contre les faux positifs des seuils fixes sur charge cyclique).
- **Alarmes** :
  - États : `OK` / `ALARM` / `INSUFFICIENT_DATA`.
  - `EvaluationPeriods` + **`DatapointsToAlarm`** (M sur N) → anti-flapping.
  - **`TreatMissingData`** : `missing` (défaut) / `notBreaching` / `breaching` / `ignore` → tombe régulièrement.
  - **Composite alarms** : combiner des alarmes avec AND/OR → réduire le bruit (n'alerter que si l'appli **et** la base sont dégradées).
  - **Actions** : SNS, **Lambda** (directement, depuis fin 2023), **Auto Scaling**, action EC2 (stop/terminate/reboot/recover), **SSM OpsItem / Incident Manager**. ⚠️ Jamais **SQS** directement. Pour toute autre cible : les changements d'état d'alarme sont aussi des **événements EventBridge**.
- **Contributor Insights** : identifier les top contributeurs (IP, clés) à partir des logs.

## 2. CloudWatch Logs — les 4 sorties à distinguer

| Besoin | Mécanisme |
|---|---|
| **Alerter** sur un pattern dans les logs (ex. `ERROR`, `404`) | **Metric filter** → métrique custom → alarme |
| **Streamer en temps réel** vers OpenSearch / Lambda / Kinesis / Firehose | **Subscription filter** |
| **Requête ad hoc / investigation** | **Logs Insights** (`fields`, `filter`, `stats`, `sort`, `limit`) |
| **Archivage long terme / analyse SQL** | **Export vers S3** (batch, jusqu'à 12 h de latence) puis **Athena** |

- **Retention** : par défaut **infinie** → toujours la configurer (question coût).
- **Subscription filter** : cibles possibles = **Kinesis Data Streams, Firehose, Lambda, OpenSearch** (via une Lambda gérée). Jamais SQS/SNS. Max 2 subscription filters par log group (+ **account-level subscription filter** pour tout le compte).
- **Cross-account/cross-region** : subscription filter → **destination** (`PutDestination` + destination policy) dans le compte central, adossée à **Kinesis Data Streams ou Firehose** (pas Lambda). C'est le pattern de centralisation des logs.
- **Data protection policies** : masquer automatiquement les données sensibles (PII, clés) dans les logs.
- **Live Tail** pour le suivi en direct pendant un déploiement.
- Sources courantes à connaître : **VPC Flow Logs** (ACCEPT/REJECT, ne capturent **pas** le contenu), **ALB/CloudFront/S3 access logs** (→ S3, analysables par Athena), **Route 53 query logs**, logs RDS/Lambda/ECS.

## 3. CloudTrail vs Config vs CloudWatch — la question du « qui/quoi/quand »

| Question | Service |
|---|---|
| **Qui** a fait cet appel d'API, quand, depuis quelle IP ? | **CloudTrail** |
| **Quelle était la configuration** de cette ressource à l'instant T, et a-t-elle changé ? | **AWS Config** |
| **Comment se comporte** la ressource (perf, erreurs, latence) ? | **CloudWatch** |

**CloudTrail**
- **Management events** (activés par défaut, 90 j d'historique dans Event history) vs **data events** (S3 objets, Lambda invoke, DynamoDB items — **volumineux et payants, désactivés par défaut**) vs **Insights events** (détection d'activité API anormale).
- **Organization trail** : un trail unique pour tous les comptes, non modifiable par les comptes membres.
- **CloudTrail Lake** : stocker et requêter les événements en **SQL** sans passer par S3 + Athena.
- ⚠️ CloudTrail livre les fichiers dans S3 avec **~5 min** de délai en moyenne → pour réagir en quasi temps réel à un appel d'API, passer par **EventBridge** (les appels d'API sont des événements `AWS API Call via CloudTrail`).
- **Log file validation** + **digest files** → prouver que les logs n'ont pas été altérés. Compléter avec **S3 Object Lock** et un bucket dans un compte dédié.
- Envoi vers **CloudWatch Logs** → metric filter → alarme (ex. alerte sur `ConsoleLogin` sans MFA ou sur `DeleteTrail`).

**AWS Config**
- **Configuration items** et **timeline** des changements ; **rules** (managed, custom Lambda, ou **Guard**), **conformance packs**, **remediation** via SSM Automation.
- **Aggregator** multi-comptes / multi-régions pour une vue de conformité centralisée.

## 4. Traçabilité applicative

- **X-Ray** : traces distribuées, **service map**, segments/subsegments, **sampling rules**, **annotations** (indexées, filtrables) vs **metadata** (non indexées). Réponse à « identifier quel microservice cause la latence ».
- **ADOT** (AWS Distro for OpenTelemetry) si la question parle de standard ouvert / multi-backends.
- **Container Insights** (ECS/EKS) et **Lambda Insights** : métriques détaillées au niveau tâche/pod/fonction.
- **CloudWatch Synthetics** : **canaries** (heartbeat, API, broken link checker, GUI workflow) → tester la disponibilité **depuis l'extérieur**, avant que les utilisateurs ne remontent le problème.
- **CloudWatch RUM** : télémétrie réelle côté navigateur.
- **ServiceLens** : relie métriques, logs et traces.

## 5. Centraliser et automatiser

- **Cross-account observability** : un **monitoring account** relié à des **source accounts** → dashboards, métriques, logs et traces consultables depuis un seul compte, sans copier les données.
- **Dashboards** cross-région/cross-compte, **metric streams** (→ Firehose → partenaire tiers, en quasi temps réel).
- **EventBridge** : le cœur de l'automatisation. Règles sur **event pattern** ou **schedule**, cibles multiples (Lambda, SSM Automation, Step Functions, SNS…), **archive + replay**, **bus cross-compte**, **API destinations** (webhooks vers un outil externe type PagerDuty/Slack).
- Chaîne type d'auto-remédiation : **événement / alarme → EventBridge → SSM Automation ou Lambda → correction + notification**.
- **Firehose** pour la livraison managée (buffering, transformation Lambda, compression) vers S3 / OpenSearch / Redshift. **OpenSearch** pour la recherche et les dashboards sur gros volumes de logs.

---

## Réflexes pour répondre aux questions

1. **« Métrique mémoire ou disque sur EC2 »** → **CloudWatch agent** (jamais disponible nativement).
2. **« Alerter quand un mot-clé apparaît dans les logs »** → **metric filter + alarme**.
3. **« Envoyer les logs en temps réel vers OpenSearch »** → **subscription filter** (pas d'export S3, trop lent).
4. **« Centraliser les logs de 50 comptes »** → subscription filters → **destination Kinesis/Firehose** dans le compte central.
5. **« Qui a supprimé cette ressource ? »** → **CloudTrail**. **« À quoi ressemblait sa config avant ? »** → **AWS Config**.
6. **« Prouver que les logs d'audit sont intacts »** → **log file validation** + bucket dédié + **Object Lock**.
7. **« Trop d'alertes, on ne veut être réveillé que si plusieurs conditions »** → **composite alarm**.
8. **« Faux positifs pendant les pics quotidiens »** → **anomaly detection** ou `DatapointsToAlarm`.
9. **« L'alarme reste en INSUFFICIENT_DATA »** → régler **`TreatMissingData`**.
10. **« Détecter une panne avant les utilisateurs »** → **Synthetics canary**.
11. **« Quel service ralentit la requête ? »** → **X-Ray**.
12. **« Analyser des téraoctets de logs dans S3 sans infra »** → **Athena** (+ partitionnement, format Parquet pour le coût).
13. **« Réduire la facture CloudWatch Logs »** → retention + export S3/Glacier + filtrer à la source.

---

## Mémo dernière minute — les 5 points à réviser en priorité

### 1. Les 4 sorties de CloudWatch Logs
**Metric filter** = alerter sur un pattern · **Subscription filter** = streamer en temps réel · **Logs Insights** = requêter à la main · **Export S3 + Athena** = archiver et analyser en masse (latence jusqu'à 12 h).

### 2. CloudTrail vs Config vs CloudWatch
Qui a appelé l'API → **CloudTrail** · État et historique de configuration → **Config** · Performance et santé → **CloudWatch**.
Data events CloudTrail = **désactivés par défaut** et coûteux (S3 objets, Lambda invoke).

### 3. Les réglages d'alarme qui tombent
`EvaluationPeriods` + **`DatapointsToAlarm`** (M sur N) · **`TreatMissingData`** (missing / notBreaching / breaching / ignore) · **composite alarm** pour combiner · actions possibles : SNS, **Lambda**, ASG, **EC2 recover/reboot**, **SSM OpsItem / Incident Manager** — jamais SQS.

### 4. Ce que CloudWatch ne voit pas tout seul
**Mémoire, disque, processus** sur EC2 → agent CloudWatch obligatoire.
Métriques custom depuis du code → `PutMetricData` ou **EMF**.

### 5. Centralisation multi-comptes
Logs → subscription filter vers une **destination** (Kinesis Data Streams ou Firehose — pas Lambda, pas SQS) dans le compte central.
Métriques/dashboards/traces → **cross-account observability** (monitoring account + source accounts).
Audit → **organization trail** CloudTrail + **aggregator** Config.
