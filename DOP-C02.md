---
tags:
  - aws
  - certification
  - dop-c02
examen: 2026-10-08
statut: en-cours
---

# DOP-C02 — AWS Certified DevOps Engineer Professional

> [!info] Repères
> **Date d'examen :** jeudi 8 octobre 2026
> **Format :** 75 questions (65 notées + 10 non notées) / 180 min → **~2 min 20 par question**
> **Score de passage :** 750 / 1000 — modèle compensatoire, pas besoin de passer chaque domaine
> **Langue :** anglais (pas de version française disponible)

> [!tip] Aménagement ESL +30 min
> Candidat non anglophone → tu peux demander l'aménagement **« ESL +30 »** (30 min supplémentaires) dans ton compte AWS Certification (*Request exam accommodations*). Il s'applique aux examens planifiés **après** son approbation → vérifier que le mail de confirmation du 8 octobre indique bien **210 min**.

## Pondération des domaines

| # | Domaine | Poids | Fiche | Test 1 (19 sept) |
|---|---------|-------|-------|------------|
| 1 | SDLC Automation | 22% | [[DOP-C02-SDLC-Automation]] | ? % |
| 2 | Configuration Management & IaC | 17% | [[DOP-C02-Configuration-Management-IaC]] | ? % |
| 3 | Resilient Cloud Solutions | 15% | [[DOP-C02-Resilient-Cloud-Solutions]] | ? % |
| 4 | Monitoring & Logging | 15% | [[DOP-C02-Monitoring-and-Logging]] | ? % |
| 5 | Incident & Event Response | 14% | [[DOP-C02-Incident-and-Event-Response]] | ? % |
| 6 | Security & Compliance | 17% | [[DOP-C02-Security-and-Compliance]] | ? % |

Relecture express de la veille : [[DOP-C02-Fiche-Flash]].

---

## 🏁 Plan jusqu'au 8 octobre — 19 jours, sans vidéos

> [!important] Principe
> **Les fiches remplacent les vidéos, les questions TD remplacent le hands-on.** Chaque explication TD (y compris celles des **mauvaises** réponses) vaut plus qu'une vidéo par minute investie.
> Vidéo Maarek **uniquement** pour un sujet raté 2 fois en question, à 2x, et juste la vidéo concernée.
> Point de départ : **28 %** le 19 sept. Il faut gagner ~50 points en 19 jours → **une séance par jour, sans exception**.

**Séance type (1h30 à 2h)**
1. 10 min — rappel actif : réécrire de tête les points clés de la séance précédente, puis comparer avec la fiche.
2. 20 min — lire la **section de la fiche** du jour (pas toute la fiche).
3. 50 min — **questions TD en mode section-based** sur ce thème. Lire l'explication de **chaque** option, même quand la réponse est bonne.
4. 15 min — chaque erreur → une règle d'une ligne dans [[#❌ Erreurs récurrentes]].

### Phase 1 — apprendre domaine par domaine (20 → 25 sept)

| Date | Thème | Fiche |
|------|-------|-------|
| dim. 20 | CodeCommit, CodeBuild, CodePipeline | [[DOP-C02-SDLC-Automation]] §1-3, §5 |
| lun. 21 | CodeDeploy + stratégies de déploiement + Elastic Beanstalk | [[DOP-C02-SDLC-Automation]] §4, §6 + tables du hub |
| mar. 22 | CloudFormation (policies, helpers, StackSets, custom resources) | SDLC §7 + [[DOP-C02-Configuration-Management-IaC]] §1-2 |
| mer. 23 | Systems Manager + Organizations / Control Tower + ASG | [[DOP-C02-Configuration-Management-IaC]] §3-6 |
| jeu. 24 | IAM, tri des services de sécurité | [[DOP-C02-Security-and-Compliance]] §1-2 |
| ven. 25 | KMS, réseau, remédiation sécurité | [[DOP-C02-Security-and-Compliance]] §3-5 |

### ✅ Checkpoint 1 — sam. 26 sept : blanc chronométré complet (set non vu) → cible **≥ 55 %**

### Phase 2 — finir le programme + corriger (27 sept → 2 oct)

| Date | Thème | Fiche |
|------|-------|-------|
| dim. 27 | Correction du blanc : relire **toutes** les explications des erreurs | — |
| lun. 28 | CloudWatch metrics/alarms/logs, CloudTrail vs Config | [[DOP-C02-Monitoring-and-Logging]] §1-3 |
| mar. 29 | X-Ray, centralisation, EventBridge + gestion des échecs | Monitoring §4-5 + [[DOP-C02-Incident-and-Event-Response]] §1-2 |
| mer. 30 | Dépannage (CFN, CodeDeploy, ECS, ASG, Lambda) + outils d'incident | [[DOP-C02-Incident-and-Event-Response]] §3-4 |
| jeu. 1 | DR, Route 53 / Global Accelerator, données, SQS | [[DOP-C02-Resilient-Cloud-Solutions]] |
| ven. 2 | **Domaine le plus faible** du checkpoint 1 | — |

### ✅ Checkpoint 2 — sam. 3 oct : blanc chronométré complet (set non vu) → cible **≥ 70 %**

> [!warning] Point de décision
> **< 65 % le 3 octobre → reporter l'examen** (possible jusqu'au 7 octobre, 24 h avant). Mieux vaut 2 semaines de plus qu'un échec + 14 jours d'attente obligatoire + 300 $.

### Phase 3 — consolider (4 → 8 oct)

| Date | Programme |
|------|-----------|
| dim. 4 | Correction du blanc + [[#❌ Erreurs récurrentes]] |
| lun. 5 | Les 2 domaines les plus faibles, en section-based |
| mar. 6 | Dernier blanc chronométré (set non vu, ou set officiel Skill Builder de 20 questions) → cible **≥ 80 %** |
| mer. 7 | [[DOP-C02-Fiche-Flash]] + [[#❌ Erreurs récurrentes]]. **Rien de nouveau.** Coucher tôt. |
| **jeu. 8** | Fiche Flash le matin (15 min max) → 🎯 |

### Journal des blancs

| Date | Test | Score | Domaine le plus faible |
|------|------|-------|------------------------|
| 19 sept | 1er test (chrono) | 21/75 — **28 %** | À compléter (révisé avant : IaC + Incident uniquement) |
| 26 sept | Checkpoint 1 | | |
| 3 oct | Checkpoint 2 | | |
| 6 oct | Blanc final | | |

---

## 🧠 Technique d'examen

- **Lire la dernière phrase en premier** : c'est la vraie question et la contrainte (*LEAST operational overhead*, *MOST cost-effective*, *MINIMUM downtime*, *FASTEST recovery*). Puis lire le scénario en cherchant les mots qui éliminent.
- **Éliminer d'abord** : sur 4 options, 2 sont en général fausses pour une raison technique claire (service qui ne fait pas ça, cible non supportée, action manuelle).
- **Règle de tri** : face à deux options plausibles → le **plus managé**, le **plus automatisé**, le **moins de code maison**. Polling/cron, scripts sur EC2, actions manuelles dans la console = presque toujours faux.
- **Questions à réponses multiples** (« Choose TWO/THREE ») : aucune note partielle — chaque option doit être vraie **et** répondre à la contrainte.
- **Gestion du temps** : 1er passage en marquant (*flag*) tout ce qui dépasse 3 min, puis retour. Ne jamais laisser de question vide (pas de pénalité).
- Les 10 questions non notées sont indiscernables → ne pas paniquer sur une question totalement inconnue.

---

## 📊 Tables de décision

### Elastic Beanstalk — politiques de déploiement

| Politique | Downtime | Capacité pendant | Rollback | Quand la choisir |
|-----------|----------|------------------|----------|------------------|
| All at once | **Oui** | Tombe à 0 | Redéployer l'ancienne version | Dev/test, le plus rapide |
| Rolling | Non | **Réduite** (1 batch hors service) | Redéployer (lent) | Prod qui tolère une baisse de capacité, sans surcoût |
| Rolling with additional batch | Non | **Maintenue** (batch supplémentaire lancé d'abord) | Redéployer (lent) | Prod, pleine capacité, surcoût faible |
| Immutable | Non | Maintenue (instances neuves dans un **ASG temporaire**) | **Rapide** : terminer les nouvelles instances | Prod critique, déploiement le plus sûr |
| Traffic splitting | Non | Maintenue | **Rapide** et automatique si la santé se dégrade | Canary : tester sur X % du trafic réel |
| Blue/Green (swap URL) | Non | Double (2 environnements) | **Instantané** : re-swap du CNAME | Changement majeur (plateforme, version runtime). ⚠️ Pas une policy EB — `SwapEnvironmentCNAMEs`. DB **hors** d'EB. |

### CodeDeploy — in-place vs blue/green

| Besoin | Choix | Pourquoi pas l'autre |
|--------|-------|----------------------|
| Pas de budget pour doubler la flotte, serveurs on-prem | **In-place** | Blue/green impossible on-prem et double temporairement la capacité |
| Rollback instantané, aucune instance de prod modifiée | **Blue/green** | In-place = rollback = redéploiement sur les mêmes instances |
| Lambda ou ECS | **Blue/green** (seul mode possible) | In-place n'existe que pour EC2/on-prem |
| Tester la nouvelle version avant de basculer le trafic | **Blue/green** + hooks (`AfterAllowTestTraffic` ECS, `BeforeAllowTraffic` Lambda) | In-place ne permet pas de tester à côté de la prod |
| Réduire le blast radius | Blue/green **canary / linear** + alarme + auto-rollback | In-place `OneAtATime` est lent et touche quand même des instances de prod |

### Qui répond à quelle question ?

| Question posée | Service |
|----------------|---------|
| Qui a fait quoi, quand ? | **CloudTrail** |
| Dans quel état était cette ressource le 3 mars ? | **AWS Config** (timeline) |
| Comportement anormal / compromission ? | **GuardDuty** |
| CVE et vulnérabilités sur mes instances ? | **Inspector** |
| Données sensibles dans S3 ? | **Macie** |
| Agrégation de findings + benchmarks ? | **Security Hub** |
| Investigation post-incident ? | **Detective** |
| Qui a accès à mes ressources depuis l'extérieur ? | **IAM Access Analyzer** |
| AWS a-t-il un problème qui me touche ? | **AWS Health** |
| Bonnes pratiques coût / sécu / limites de service ? | **Trusted Advisor** |
| Quel microservice ralentit la requête ? | **X-Ray** |
| Anomalie opérationnelle sans seuil défini ? | **DevOps Guru** |

### Secrets Manager vs Parameter Store

| Critère | Secrets Manager | Parameter Store |
|---------|-----------------|-----------------|
| Rotation automatique | **Native** (Lambda gérée RDS/Redshift/DocumentDB) | Non — à coder soi-même |
| Coût | Payant par secret | Gratuit (standard) |
| Taille max | 64 Ko | 4 Ko (8 Ko advanced) |
| Cross-compte | Oui (resource policy) | Tier advanced via RAM |
| Multi-région | Réplication native | Non |
| Réflexe | « rotation », « credentials de base » | « config », « hiérarchie », « budget » |

### Pièges de logging à retenir

- Un **subscription filter** cible Kinesis Data Streams, Firehose, Lambda ou OpenSearch — **jamais SQS ni SNS**.
- **Cross-account** : destination adossée à **Kinesis Data Streams ou Firehose** (pas Lambda).
- **Alarmes CloudWatch** → SNS, **Lambda**, Auto Scaling, actions EC2, SSM OpsItem/Incident Manager — **jamais SQS directement**. Pour le reste : EventBridge.
- **Export S3** des logs = batch, jusqu'à 12 h → jamais la réponse pour du temps réel.
- **Mémoire / disque EC2** → CloudWatch agent, jamais natif.

---

## 📚 Ressources

- Tutorials Dojo Practice Exams DOP-C02 2026 — accès jusqu'au 28 août 2027 → **la ressource n°1 cette semaine**
- Cheat sheets Tutorials Dojo, en particulier les pages de comparaison
- AWS Skill Builder — set officiel de 20 questions (bon test de calibrage, style exact de l'examen)
- [Exam Guide officiel](https://docs.aws.amazon.com/aws-certification/latest/devops-engineer-professional-02/devops-engineer-professional-02.html)
- Cours Maarek (Udemy) — en **référence ponctuelle** seulement (une vidéo précise sur un sujet raté)

> [!warning] Braindumps
> ExamTopics et similaires : interdits par le AWS Certification Program Agreement. Risque de révocation de toutes mes certifications AWS. Et de toute façon mauvais pour apprendre — pas d'explication des mauvaises options.

---

## ❌ Erreurs récurrentes

> Chaque erreur de blanc atterrit ici, reformulée en règle. Relire cette section avant chaque blanc.
