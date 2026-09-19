---
tags: [dop-c02, aws, devops, resilience, dr]
domaine: "3 — Resilient Cloud Solutions (15% de l'examen)"
---

# DOP-C02 — Domaine 3 : Resilient Cloud Solutions

> Poids : **15%**.
> Trois axes : haute disponibilité, scalabilité, récupération automatisée selon **RTO/RPO**.
> Angle des questions : on te donne toujours un **RTO**, un **RPO** et une **contrainte de coût** → la bonne réponse est la solution la **moins chère** qui tient les deux objectifs. Pas la plus robuste.

---

## 1. Le socle : RTO / RPO et les 4 stratégies de DR

- **RPO** = perte de données acceptable (on regarde **en arrière** : fréquence des sauvegardes).
- **RTO** = temps de remise en service acceptable (on regarde **en avant** : vitesse de bascule).

| Stratégie | RPO / RTO | Ce qui tourne en région DR | Coût |
|---|---|---|---|
| **Backup & Restore** | Heures / heures | Rien (juste des sauvegardes répliquées) | € |
| **Pilot Light** | Minutes / dizaines de minutes | Le **cœur de données** seulement (DB répliquée), le compute est éteint/prêt | €€ |
| **Warm Standby** | Secondes / minutes | Une copie **complète mais réduite** qui tourne réellement | €€€ |
| **Multi-site / Active-Active** | ~0 / ~0 | Tout, à pleine capacité, servant du trafic | €€€€ |

Mnémo : *Pilot light = les données sont chaudes, le compute est froid. Warm standby = tout est tiède et on scale.*

**AWS Elastic Disaster Recovery (DRS)** : réplication bloc continue de serveurs (on-prem ou EC2) vers une région cible, RPO de l'ordre de la seconde, RTO de quelques minutes. Réponse type à « répliquer des serveurs existants sans les réarchitecturer ».

## 2. Répartition du trafic et bascule

### Route 53

| Policy | Usage |
|---|---|
| Simple | Un seul enregistrement |
| **Weighted** | Répartition en %, canary, migration progressive |
| **Latency** | Router vers la région la plus rapide pour le client |
| **Failover** | Actif/passif avec health check (le classique DR) |
| Geolocation / Geoproximity | Conformité réglementaire / rapprochement géographique (bias) |
| Multivalue answer | Jusqu'à 8 réponses saines, "poor man's LB" |

- **Health checks** : endpoint, **calculated** (combinaison d'autres checks), ou basé sur une **alarme CloudWatch** (indispensable pour surveiller une ressource privée, non exposée à Internet).
- ⚠️ **Limite DNS** : le **TTL** est mis en cache côté client → bascule pas instantanée. Si la question insiste sur un failover en **secondes**, la réponse est **Global Accelerator**.
- **Route 53 ARC** (Application Recovery Controller) : **readiness checks** (la région DR est-elle vraiment prête ?) + **routing controls** (interrupteurs de bascule manuels, hautement disponibles, avec **safety rules** pour éviter de tout éteindre).

### Global Accelerator vs CloudFront

- **Global Accelerator** : 2 IP **anycast** statiques, trafic TCP/UDP sur le réseau AWS, **failover régional en quelques secondes** sans dépendre du DNS. Idéal pour les protocoles non-HTTP et les IP fixes (whitelisting).
- **CloudFront** : cache HTTP en edge, **origin groups** avec **origin failover** (sur codes 4xx/5xx configurables).

### Load balancers

- **ALB** (L7, HTTP), **NLB** (L4, IP statique/Elastic IP par AZ, ultra faible latence), **GWLB** (appliances réseau).
- **Cross-zone** : **activé par défaut et gratuit sur ALB**, **désactivé par défaut sur NLB** (et facturé entre AZ).
- **Deregistration delay** (connection draining) pour ne pas couper les requêtes en cours.
- Health checks ELB + **health check type `ELB`** sur l'ASG (sinon l'ASG ne voit que l'état EC2, pas l'appli qui plante).

## 3. Données : disponibilité et réplication

| Service | HA intra-région | Cross-région |
|---|---|---|
| **RDS Multi-AZ (instance)** | Réplication **synchrone**, standby **non lisible**, failover DNS 60–120 s | Non |
| **RDS Multi-AZ DB cluster** | 1 writer + **2 standbys lisibles**, failover < 35 s | Non |
| **RDS read replica** | Asynchrone, **lisible** | **Oui**, promotion manuelle → DR |
| **Aurora** | 6 copies / 3 AZ, réplicas promus automatiquement | **Global Database** : réplication < 1 s, RTO < 1 min, RPO ~1 s |
| **DynamoDB** | Multi-AZ par défaut | **Global Tables** : actif/actif multi-régions |
| **S3** | 11 nines | **CRR** (+ **RTC** pour un SLA de 15 min) |
| **EFS** | Multi-AZ (Regional) | Replication EFS |
| **ElastiCache Redis** | Multi-AZ + auto-failover | Global Datastore |

- **RDS Proxy** : mutualise les connexions et **réduit le temps de failover** (~66%) ; évite les tempêtes de connexions depuis Lambda.
- **Aurora** extras : **Backtrack** (rembobiner sans restaurer), **cloning** rapide, **Serverless v2** pour les charges imprévisibles.
- **DynamoDB** : **PITR** (35 jours), on-demand vs provisioned + auto scaling, **DAX** pour le cache microseconde.

## 4. Sauvegardes

- **AWS Backup** : plans (fréquence, fenêtre, lifecycle vers cold storage), **vaults**, **copie cross-région et cross-compte**, **Backup Policies** via Organizations pour imposer la politique à tous les comptes.
- **Vault Lock** : mode **governance** (contournable par un rôle privilégié) vs mode **compliance** (**irréversible** après un délai de grâce de 3 jours minimum, personne ne peut supprimer, même root). Réponse type à « protéger les sauvegardes contre une suppression malveillante » → compliance mode, comme **S3 Object Lock**.
- **DLM (Data Lifecycle Manager)** : cycle de vie automatisé des snapshots EBS / AMI par tags. Plus léger qu'AWS Backup si on ne gère que de l'EBS.

## 5. Scalabilité et découplage

- **Auto Scaling** : **target tracking** (le défaut à privilégier), step, scheduled, **predictive** (ML, charges cycliques). Warm pools pour les apps longues à démarrer.
- **ECS/EKS** : service auto scaling, **capacity providers** (avec managed scaling), **Karpenter**/Cluster Autoscaler côté EKS, `minimumHealthyPercent`.
- **Lambda** : **reserved concurrency** (plafonne et garantit une part du quota) vs **provisioned concurrency** (élimine le cold start). Attention au quota régional partagé.
- **Découplage = résilience** :
  - **SQS** : tampon absorbant les pics, **visibility timeout** (≥ durée de traitement), **DLQ** après N échecs (`maxReceiveCount`), FIFO pour l'ordre et la déduplication.
  - **SNS** → fan-out, avec DLQ par souscription.
  - **EventBridge** → routage par pattern, **archive + replay** pour rejouer les événements perdus.
  - **Kinesis Data Streams** → rétention (jusqu'à 365 j), rejeu possible, ordre par shard.
- Patterns à reconnaître : **retry avec backoff exponentiel + jitter**, **idempotence**, **circuit breaker**, **static stability** (la région DR ne doit pas dépendre d'un scaling au moment du sinistre).
- **AWS Fault Injection Service (FIS)** : tester la résilience par injection de pannes (chaos engineering) — la réponse à « comment valider que notre bascule fonctionne vraiment ? ». Conditions d'arrêt sur **alarme CloudWatch**.
- **AWS Resilience Hub** : déclarer des objectifs RTO/RPO pour une appli, **évaluer** si l'architecture les tient, recommandations + tests FIS. Réponse à « vérifier en continu que l'appli respecte ses objectifs de résilience ».

---

## Réflexes pour répondre aux questions

1. **« RTO de quelques minutes, coût maîtrisé »** → **Pilot Light** (ou Warm Standby si l'appli doit déjà servir du trafic).
2. **« Failover en secondes, le DNS est trop lent »** → **Global Accelerator**.
3. **« DR cross-région pour une base relationnelle »** → **Aurora Global Database**, ou **cross-region read replica** promue si c'est du RDS classique.
4. **« Actif/actif multi-régions sur du NoSQL »** → **DynamoDB Global Tables**.
5. **« Les backups doivent être indestructibles, même par un admin »** → **Vault Lock compliance** / **S3 Object Lock**.
6. **« Tempête de connexions à la base après un failover »** → **RDS Proxy**.
7. **« L'ASG ne remplace pas une instance dont l'appli est plantée »** → health check type **ELB** au lieu de EC2.
8. **« Pics de charge imprévisibles qui écroulent le backend »** → découplage par **SQS**.
9. **« Messages perdus / en échec répété »** → **DLQ** (+ vérifier le visibility timeout).
10. **« Surveiller une ressource privée avec Route 53 »** → health check basé sur une **alarme CloudWatch**.
11. Si une option repose sur une **intervention humaine** pour basculer alors que le RTO est court, elle est fausse.

---

## Mémo dernière minute — les 5 points à réviser en priorité

### 1. Les 4 stratégies de DR
Backup & Restore (heures) < Pilot Light (données chaudes, compute froid) < Warm Standby (tout tourne en réduit) < Active-Active (~0).
La question donne RTO + RPO + budget → choisir la **moins chère qui tient**.

### 2. Route 53 vs Global Accelerator
Route 53 failover = DNS, limité par le **TTL** → minutes.
Global Accelerator = IP anycast, bascule en **secondes**, non-HTTP, IP fixes.
Health check Route 53 sur ressource privée → via **alarme CloudWatch**.

### 3. RDS Multi-AZ vs Read Replica vs Aurora Global
Multi-AZ = **HA**, synchrone, standby **non lisible**, même région.
Read replica = **scalabilité en lecture**, asynchrone, **cross-région possible**, promotion manuelle = DR.
Aurora Global Database = DR cross-région managé, RPO ~1 s / RTO < 1 min.

### 4. AWS Backup et Vault Lock
Plans + vaults + copies **cross-région/cross-compte** + Backup Policies Organizations.
**Governance** = contournable par un rôle autorisé · **Compliance** = **irréversible**, même pour root.
DLM = alternative légère, snapshots EBS/AMI par tags uniquement.

### 5. SQS : les 3 réglages qui tombent
**Visibility timeout** trop court → message traité en double. **`maxReceiveCount` + DLQ** → isoler les poison pills. **Long polling** → réduire les appels à vide.
Et toujours : le consommateur doit être **idempotent**.
