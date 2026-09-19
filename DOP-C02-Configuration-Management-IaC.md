---
tags: [dop-c02, aws, devops, iac, config-management]
domaine: "2 — Configuration Management and IaC (17% de l'examen)"
---

# DOP-C02 — Domaine 2 : Configuration Management and IaC

> Poids : **17%**.
> Trois axes : (1) définir de l'infra réutilisable, (2) créer/sécuriser des comptes à grande échelle, (3) automatiser des tâches complexes sur de grandes flottes.
> Angle des questions : « comment **standardiser** et **réutiliser** sans intervention manuelle, sur N comptes et N régions ? »

---

## 1. CloudFormation — les mécanismes de réutilisation

| Mécanisme | Portée | Quand le choisir |
|---|---|---|
| **Nested stacks** | 1 compte / 1 région | Composants réutilisés **dans** une même stack (ex. un LB standard). Update par la stack parente. |
| **Cross-stack** (`Export` / `Fn::ImportValue`) | 1 compte / **1 région** | Partager une valeur entre stacks au cycle de vie **différent** (ex. VPC ID). ⚠️ Impossible de supprimer/modifier un export tant qu'il est importé. |
| **StackSets** | **Multi-comptes / multi-régions** | Déployer le même template partout (baseline sécurité, rôles, Config rules). |
| **Modules** | Réutilisation de blocs | Encapsuler un ensemble de ressources conforme, réutilisable dans plusieurs templates. |
| **SSM Parameter Store** | 1 région (paramètres **advanced** partageables cross-compte via **RAM**) | Découpler producteur et consommateur sans le verrou des exports. ⚠️ Parameter Store est **régional** : CFN ne lit un paramètre que dans **sa** région. |
| **Custom resource (Lambda)** | Cross-région | Lire une valeur (output, paramètre) dans une **autre région** — `Fn::ImportValue` et `{{resolve:ssm}}` ne franchissent pas les régions. |

**Réflexe** : *même stack → nested · même compte + même région → export (ou SSM) · autre région → custom resource Lambda, ou écrire la valeur dans chaque région via StackSets · même template partout → StackSets*.

### StackSets — à connaître précisément

- **Self-managed permissions** : tu crées toi-même `AWSCloudFormationStackSetAdministrationRole` (compte admin) et `AWSCloudFormationStackSetExecutionRole` (comptes cibles).
- **Service-managed permissions** : intégré à **AWS Organizations**, cible des **OU** entières, active l'**automatic deployment** → tout nouveau compte qui rejoint l'OU reçoit la stack automatiquement (et la perd s'il en sort). C'est la réponse aux questions « nouveaux comptes ».
- **Operation preferences** : `MaxConcurrentCount`, `FailureToleranceCount`, déploiement par région séquentiel ou parallèle.
- **Drift detection** disponible au niveau du StackSet.

### Autres éléments CloudFormation

- **Custom resources** (Lambda / SNS) : tout ce que CFN ne gère pas nativement (vider un bucket avant delete, appeler une API tierce). Doit renvoyer une réponse **SUCCESS/FAILED sur l'URL pré-signée**, sinon la stack reste bloquée jusqu'au timeout.
- **Macros / `Transform`** : transformer le template au déploiement (`AWS::Serverless` = SAM, `AWS::Include` = extraits partagés).
- **Registry / third-party resource types** : provisionner des ressources non-AWS (Datadog, MongoDB…) depuis CFN.
- **Dynamic references** : `{{resolve:ssm:nom:version}}`, `{{resolve:ssm-secure:...}}`, `{{resolve:secretsmanager:...}}` → jamais de secret dans un template.
- **Parameter types SSM** : `AWS::SSM::Parameter::Value<String>` → récupérer la dernière AMI sans coder l'ID en dur (`/aws/service/ami-amazon-linux-latest/...`).
- **Service role** : CFN assume un rôle dédié → l'utilisateur n'a pas besoin des permissions sur les ressources, seulement sur CFN. Bon pattern de moindre privilège.
- **Termination protection**, **stack policy**, **change sets**, **drift detection** : voir fiche domaine 1.

## 2. Les autres outils IaC

- **AWS CDK** : code (TS, Python, Java…) → **synthétise** un template CloudFormation (`cdk synth`, `cdk deploy`). Utile pour la logique conditionnelle complexe et les **constructs** réutilisables. Permet de tester l'infra avec des frameworks de test classiques.
- **AWS SAM** : sur-ensemble de CFN pour le serverless (`AWS::Serverless::Function/Api/StateMachine`). `sam local` pour tester en local, `AutoPublishAlias` + `DeploymentPreference` pour le canary Lambda.
- **OpsWorks** (Chef/Puppet) : **fin de vie en 2024**. S'il apparaît dans une réponse, c'est presque toujours un **distracteur** → préférer SSM (State Manager, Run Command).
- **Elastic Beanstalk** : `.ebextensions/*.config` (packages, files, commands, container_commands, option_settings), **saved configurations** pour cloner un environnement, custom AMI ou **custom platform** pour accélérer les démarrages.
- **Service Catalog** : produits (templates CFN) regroupés en **portfolios**, partagés aux utilisateurs finaux. **Launch constraint** = un rôle IAM utilisé pour le lancement → l'utilisateur provisionne sans avoir les permissions sur les ressources. **TagOptions** pour forcer le tagging. C'est la réponse type à « self-service pour les développeurs, avec des garde-fous ».

## 3. AWS Systems Manager — quelle feature pour quel besoin

| Besoin                                               | Feature                                                                                      |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Exécuter une commande ad hoc sur une flotte          | **Run Command** (document SSM, ciblage par **tags** ou resource group)                       |
| Maintenir un état dans le temps / corriger la dérive | **State Manager** (association, planning cron/rate, réapplique la config)                    |
| Patcher un parc selon des règles                     | **Patch Manager** (patch **baselines**, patch groups via tag `Patch Group`, scan vs install) |
| Fenêtre planifiée pour les actions perturbantes      | **Maintenance Windows** (tâches Run Command / Automation / Lambda / Step Functions)          |
| Runbook multi-étapes avec approbations               | **Automation** (documents `aws:executeScript`, `aws:approve`, branchements)                  |
| Accès shell sans SSH ni bastion ni port 22           | **Session Manager** (logs vers S3/CloudWatch, IAM + KMS)                                     |
| Inventaire logiciel / conformité                     | **Inventory** + **Compliance**                                                               |
| Déployer des packages logiciels                      | **Distributor**                                                                              |
| Serveurs on-prem                                     | **Hybrid activations** (managed instances `mi-…`)                                            |
| Config / secrets                                     | **Parameter Store**                                                                          |

⚠️ Prérequis systématiques : **agent SSM** installé + **rôle IAM d'instance** (`AmazonSSMManagedInstanceCore`) + connectivité (NAT ou **VPC endpoints** `ssm`, `ssmmessages`, `ec2messages`). Une question « l'instance n'apparaît pas dans Fleet Manager » teste toujours l'un de ces trois points.

### Parameter Store vs Secrets Manager

| | Parameter Store | Secrets Manager |
|---|---|---|
| Coût | Gratuit (standard) | Payant par secret |
| Taille | 4 Ko (8 Ko advanced) | 64 Ko |
| Rotation | Manuelle (via Lambda maison) | **Native**, Lambda gérée pour RDS/Redshift/DocumentDB |
| Chiffrement | Optionnel (`SecureString` + KMS) | Toujours |
| Cross-account | Tier **advanced** uniquement, via **RAM** | **Oui** (resource policy + key policy KMS) |
| Multi-région | Non | **Réplication native** des secrets |
| Versions | Oui | Oui (staging labels `AWSCURRENT` / `AWSPREVIOUS`) |

Réflexe : *rotation automatique demandée → Secrets Manager. Config non sensible ou budget serré → Parameter Store.*

## 4. Multi-comptes : création et sécurisation

- **AWS Organizations** : racine → **OU** → comptes. **SCPs** = garde-fous de type `Deny` : elles **plafonnent** les permissions, elles n'en accordent jamais. Ne s'appliquent **pas** au compte de gestion. Une action doit être autorisée par **IAM ET SCP**.
- **RCPs** (Resource Control Policies) : pendant des SCPs côté **ressources** (S3, KMS, STS, SQS, Secrets Manager…) → plafonner ce que des principaux **externes** peuvent faire sur tes ressources (« data perimeter »).
- **Tag policies**, **backup policies** et **declarative policies** (ex. imposer IMDSv2, bloquer l'accès public aux AMI/snapshots) au niveau Organizations pour standardiser.
- **Delegated administrator** : déléguer la gestion d'un service (StackSets, Config, Security Hub, GuardDuty…) à un compte membre plutôt que d'utiliser le compte de gestion.
- **Control Tower** : landing zone clés en main (multi-comptes, log archive + audit accounts, IAM Identity Center, CloudTrail org trail).
  - **Account Factory** : provisioning standardisé de comptes (basé sur Service Catalog).
  - **Guardrails / controls** : **preventive** (implémentées par SCP) vs **detective** (implémentées par **AWS Config rules**) vs **proactive** (CloudFormation hooks). Statuts : *Enforced* / *Not enabled* pour les preventives, *Clear* / *In violation* pour les detectives.
  - **CfCT** (Customizations for Control Tower) : pipeline pour appliquer tes propres templates/SCPs aux comptes créés.
- Sans Control Tower : `organizations:CreateAccount` (asynchrone → suivre avec `DescribeCreateAccountStatus`), puis StackSets service-managed sur l'OU pour la baseline.
- **IAM Identity Center** : permission sets, accès fédéré multi-comptes (remplace les rôles cross-account manuels).
- **RAM** : partager des ressources (subnets, Transit Gateway, licences) entre comptes plutôt que les dupliquer.

**Réflexe compte neuf** : *Control Tower Account Factory pour créer → StackSets service-managed (auto-deployment sur l'OU) pour la baseline → SCP pour les interdictions → Config rules pour la détection.*

## 5. Golden AMIs et flottes EC2

- **EC2 Image Builder** : **components** (build + test) → **recipe** (AMI de base + components) → **pipeline** (planning cron ou déclenché) → **distribution settings** (copie multi-régions, partage cross-comptes, mise à jour de launch templates). Remplace un pipeline Packer maison ; réponse type à « pipeline d'AMI durcies, testées et distribuées ».
- **Launch templates** (versionnés) — les **launch configurations** sont l'ancienne génération, non modifiables, à éviter dans les réponses.
- **Auto Scaling** :
  - **Instance refresh** : remplacer progressivement les instances après une nouvelle AMI (`MinHealthyPercentage`, `InstanceWarmup`, **checkpoints** pour valider par paliers, rollback possible).
  - **Lifecycle hooks** : mettre l'instance en `Pending:Wait` / `Terminating:Wait` → installer du logiciel ou récupérer les logs avant terminaison. `CompleteLifecycleAction` (ou heartbeat timeout) pour débloquer.
  - **Warm pools** : instances pré-initialisées et arrêtées → démarrage rapide pour les apps longues à booter.
  - **Mixed instances policy** + Spot pour le coût ; scaling **target tracking** (défaut recommandé), **step**, **scheduled**, **predictive**.

## 6. Automatiser les tâches complexes

- **EventBridge** (règle sur event pattern ou schedule) → Lambda / SSM Automation / Step Functions : le socle de toute automatisation événementielle.
- **Step Functions** pour les workflows longs, avec branchements, retries et gestion d'erreur explicites (au lieu d'enchaîner des Lambdas).
- **SSM Automation** pour les runbooks opérationnels sur des ressources AWS (redémarrer, snapshot, remédier).
- **AWS Config remediation** : associer une action SSM Automation à une règle non conforme → auto-remédiation.
- **AWS Batch / Fargate** pour les traitements par lot volumineux.
- **Lambda** limitée à 15 min → si le traitement est plus long, la bonne réponse est Step Functions, Batch, ou ECS/Fargate.

---

## Réflexes pour répondre aux questions

1. **« Appliquer une baseline à tous les comptes, y compris les futurs »** → **StackSets service-managed** + auto-deployment sur l'OU.
2. **« Empêcher une action même pour un admin du compte »** → **SCP** (pas une politique IAM).
3. **« Les développeurs doivent provisionner eux-mêmes, mais de façon contrôlée »** → **Service Catalog** + launch constraint.
4. **« La configuration dérive sur les instances »** → **State Manager** (réapplique périodiquement), pas Run Command (ponctuel).
5. **« Patcher tout le parc selon un calendrier »** → **Patch Manager** + patch baseline + Maintenance Window.
6. **« Supprimer l'accès SSH / les bastions »** → **Session Manager**.
7. **« Rotation automatique des credentials »** → **Secrets Manager**.
8. **« Partager une valeur entre deux stacks de régions différentes »** → **custom resource Lambda** qui lit l'autre région (ni `Fn::ImportValue` ni `{{resolve:ssm}}` ne traversent les régions).
9. **« Nouvelle AMI, remplacer les instances sans downtime »** → **ASG instance refresh** (ou UpdatePolicy `AutoScalingRollingUpdate` si c'est CFN).
10. **« AMI durcie construite et testée automatiquement »** → **EC2 Image Builder**.
11. Une réponse qui implique de **cliquer dans la console** ou un **script sur un serveur de build maison** est presque toujours la mauvaise.

---

## Mémo dernière minute — les 5 points à réviser en priorité

### 1. Choisir le bon mécanisme de réutilisation CFN
Nested (même stack) · Export/ImportValue (même compte **et** même région, bloque la suppression) · StackSets (multi-comptes/régions) · SSM Parameter Store (découplage, régional) · Custom resource Lambda (lire dans une autre région) · Modules (blocs conformes réutilisables).

### 2. StackSets : self-managed vs service-managed
Self-managed = 2 rôles à créer (administration + execution), ciblage par **ID de compte**.
Service-managed = **Organizations**, ciblage par **OU**, **automatic deployment** sur les nouveaux comptes. C'est la réponse dès qu'on parle de comptes futurs.

### 3. La carte des features SSM
Run Command = ponctuel · State Manager = **maintien dans le temps** · Patch Manager = patchs + baselines · Automation = runbook multi-étapes · Session Manager = accès sans SSH · Distributor = packages · Inventory = ce qui est installé.
Prérequis toujours identiques : **agent + rôle IAM + connectivité (NAT ou VPC endpoints)**.

### 4. Parameter Store vs Secrets Manager
Rotation native, 64 Ko, cross-account, payant → **Secrets Manager**.
Gratuit, 4 Ko, hiérarchique, rotation à coder soi-même → **Parameter Store**.
Réplication multi-région → **Secrets Manager**.

### 5. Control Tower : les 3 familles de controls
**Preventive** = SCP (bloque) · **Detective** = Config rule (constate) · **Proactive** = CloudFormation hook (bloque avant provisioning).
Account Factory pour créer les comptes, CfCT pour y appliquer tes propres customisations.

**Bonus fréquemment testé** : **lifecycle hook** (agir *pendant* le lancement/la terminaison) ≠ **warm pool** (démarrage rapide) ≠ **instance refresh** (remplacer la flotte après une nouvelle AMI).
